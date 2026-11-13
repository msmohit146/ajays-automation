#!/usr/bin/env python3
"""Import scans that exist on disk under images/<folder>/ but have no row in archive.db.

A scan counts as "already imported" if archive.db has a row with the same
folder_name + file_name, or a file_path whose parent folder + file name match.
Missing scans are OCR'd with the Anthropic API (same prompt/model as the other
import_missing_* scripts) and inserted with the next free ids.

Usage:
    python import_missing_all_folders.py            # dry run: list missing scans
    python import_missing_all_folders.py --run      # back up DB, OCR, insert, save
"""
import base64
import concurrent.futures as cf
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path('archive.db')
IMAGES_ROOT = Path('images')
MODEL = 'claude-sonnet-5-5'
EXTS = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}
PROMPT = 'Extract all text from this image. Provide clean, readable text.'
REPORT_PATH = Path(f'missing_import_report_{datetime.now():%Y%m%d_%H%M%S}.json')


def find_missing(conn):
    rows = conn.execute('SELECT file_name, folder_name, file_path FROM articles').fetchall()
    known = set()
    for fn, fo, fp in rows:
        parts = (fp or '').replace('\\', '/').split('/')
        known.add((fo, fn))
        if len(parts) > 1:
            known.add((parts[-2], parts[-1]))

    missing = []
    for folder in sorted(os.listdir(IMAGES_ROOT)):
        fdir = IMAGES_ROOT / folder
        if not fdir.is_dir() or folder.startswith('['):
            continue
        for name in sorted(os.listdir(fdir)):
            path = fdir / name
            if not path.is_file() or path.suffix.lower() not in EXTS:
                continue
            if (folder, name) in known:
                continue
            missing.append((folder, name, path))
    return missing


def ocr(client, path):
    data = base64.standard_b64encode(path.read_bytes()).decode('utf-8')
    media = EXTS[path.suffix.lower()]
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64', 'media_type': media, 'data': data}},
                {'type': 'text', 'text': PROMPT},
            ],
        }],
    )
    text = ''.join(b.text for b in msg.content if hasattr(b, 'text')).strip()
    return text or '[No readable text found]'


def main():
    run = '--run' in sys.argv
    conn = sqlite3.connect(DB_PATH)
    missing = find_missing(conn)

    print(f'Scans on disk with no DB row: {len(missing)}')
    by_folder = {}
    for folder, _, _ in missing:
        by_folder[folder] = by_folder.get(folder, 0) + 1
    for k, v in by_folder.items():
        print(f'  {k!r}: {v}')

    if not run:
        print('\nDry run only. Re-run with --run to back up the DB, OCR and insert.')
        conn.close()
        return

    backup = Path(f'archive_before_missing_import_{datetime.now():%Y%m%d_%H%M%S}.db')
    bk = sqlite3.connect(backup)
    conn.backup(bk)
    bk.close()
    print(f'Backup written: {backup}')

    from anthropic import Anthropic
    client = Anthropic()

    results = {}
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(ocr, client, p): (f, n, p) for f, n, p in missing}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            f, n, p = futs[fut]
            try:
                results[(f, n)] = ('ok', fut.result())
            except Exception as e:  # keep going; report failures
                results[(f, n)] = ('error', str(e))
            if i % 10 == 0 or i == len(futs):
                print(f'  OCR {i}/{len(futs)}')

    cur = conn.cursor()
    cur.execute('SELECT COALESCE(MAX(id), 0) FROM articles')
    next_id = cur.fetchone()[0] + 1

    inserted, failed = 0, []
    for folder, name, path in missing:
        status, text = results[(folder, name)]
        if status != 'ok':
            failed.append({'folder': folder, 'file': name, 'error': text})
            continue
        cur.execute(
            'INSERT INTO articles (id, file_name, folder_name, file_path, parsed_text, image_rotation) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (next_id, name, folder, f'images/{folder}/{name}', text, 0),
        )
        next_id += 1
        inserted += 1

    conn.commit()
    conn.close()

    REPORT_PATH.write_text(json.dumps({
        'backup': str(backup),
        'missing_total': len(missing),
        'inserted': inserted,
        'failed': failed,
    }, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\nInserted {inserted} rows. Failed: {len(failed)}. Report: {REPORT_PATH}')


if __name__ == '__main__':
    main()
