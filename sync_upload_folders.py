#!/usr/bin/env python3
"""Merge re-uploaded scan folders into the repo, keeping every existing scan.

Each MAPPING entry is (upload subfolder, repo subfolder, database folder label).
For each mapping:
- JPEGs in the upload that are new, or whose content changed, are copied into the repo folder.
  Repo files that are not in the upload are kept.
- PDFs in the upload are copied, and every page is rendered to JPEG (200 dpi).
  Names that already exist are written with a _pdf suffix so no scan is overwritten.
- Database: every new, changed or rendered JPEG gets AI angle detection and column-aware OCR.
  Missing rows are created, existing rows are updated. Other rows are left alone.

Usage:
    python sync_upload_folders.py <upload_root>            # dry run
    python sync_upload_folders.py <upload_root> --run
"""
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pymupdf as fitz  # PyMuPDF

import reocr_imported_with_ai as m

DB_PATH = Path('archive.db')
SCANS = Path('images') / '[SCANS]_ Ajay Srinivisan_ 14th August'
DPI = 200

MAPPING = [
    ('2001', SCANS / '2001 & 2002' / '2001', '2001'),
    ('2002', SCANS / '2001 & 2002' / '2002', '2002'),
    ('2002/merged', SCANS / '2001 & 2002' / '2002' / 'merged', '2002'),
]

m.OCR_PROMPT = ("Transcribe all the text on this newspaper/magazine scan. The page may have several columns: "
                "read each column top to bottom, one column at a time, left to right. Keep headlines, bylines, captions and "
                "boxed text separate from the body columns. Never merge or interleave lines from different columns. "
                "Output only the transcription, with paragraph breaks.")


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def repo_oids(repo_dir):
    """sha256 of files directly under repo_dir on origin/main (from LFS pointers)."""
    prefix = repo_dir.as_posix() + '/'
    ls = subprocess.run(['git', 'ls-tree', 'origin/main', '--', prefix],
                        capture_output=True, text=True).stdout.splitlines()
    out = {}
    for line in ls:
        meta, path = line.split('\t', 1)
        if '/' in path[len(prefix):]:
            continue  # only files directly in this folder
        ptr = subprocess.run(['git', 'cat-file', '-p', meta.split()[2]], capture_output=True, text=True).stdout
        oid = [l.split(':', 1)[1] for l in ptr.splitlines() if l.startswith('oid sha256:')]
        if oid:
            out[Path(path).name] = oid[0]
    return out


def render_pdf(pdf, dest_dir, taken):
    names = []
    doc = fitz.open(pdf)
    n_pages = len(doc)
    for i, page in enumerate(doc, 1):
        base = pdf.stem if n_pages == 1 else f'{pdf.stem}_p{i}'
        name = f'{base}.jpg'
        if name in taken or (dest_dir / name).exists():
            name = f'{base}_pdf.jpg'
        pix = page.get_pixmap(dpi=DPI, colorspace=fitz.csRGB)
        pix.save(dest_dir / name, jpg_quality=92)
        taken.add(name)
        names.append(name)
    doc.close()
    return names


def tree_oids(prefix_dir):
    """sha256 of every file under prefix_dir (recursive) on origin/main."""
    prefix = prefix_dir.as_posix() + '/'
    ls = subprocess.run(['git', 'ls-tree', '-r', 'origin/main', '--', prefix],
                        capture_output=True, text=True).stdout.splitlines()
    out = set()
    for line in ls:
        meta, path = line.split('	', 1)
        ptr = subprocess.run(['git', 'cat-file', '-p', meta.split()[2]], capture_output=True, text=True).stdout
        oid = [l.split(':', 1)[1] for l in ptr.splitlines() if l.startswith('oid sha256:')]
        if oid:
            out.add(oid[0])
    return out


def classify(upload_dir, repo_dir, tree_hashes):
    old = repo_oids(repo_dir)
    jpgs = sorted(p for p in upload_dir.iterdir() if p.is_file() and p.suffix.lower() == '.jpg')
    pdfs = sorted(p for p in upload_dir.iterdir() if p.is_file() and p.suffix.lower() == '.pdf')
    new, changed, same, dup = [], [], [], []
    for j in jpgs:
        h = sha256(j)
        if j.name in old:
            (same if old[j.name] == h else changed).append(j.name)
        elif h in tree_hashes:
            dup.append(j.name)  # identical scan already in the repo under another folder of this year
        else:
            new.append(j.name)
    kept = sorted(set(old) - {p.name for p in jpgs} - {p.name for p in pdfs})
    return jpgs, pdfs, new, changed, same, dup, kept


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = Path(sys.argv[1])
    run = '--run' in sys.argv

    tree = tree_oids(SCANS / '2001 & 2002')
    plans = []
    for up_sub, repo_dir, label in MAPPING:
        upload_dir = root / up_sub
        jpgs, pdfs, new, changed, same, dup, kept = classify(upload_dir, repo_dir, tree)
        plans.append((up_sub, upload_dir, repo_dir, label, jpgs, pdfs, new, changed))
        print(f'[{up_sub}] -> {repo_dir.as_posix()} ({label})')
        print(f'   upload: {len(jpgs)} JPEG, {len(pdfs)} PDF | new={len(new)} changed={len(changed)} identical={len(same)} duplicate-elsewhere={len(dup)} {dup} | kept from repo={len(kept)} {kept}')

    if not run:
        print('Dry run only. Re-run with --run.')
        return

    conn = sqlite3.connect(DB_PATH)
    backup = Path(f'archive_before_upload_sync_{datetime.now():%Y%m%d_%H%M%S}.db')
    bk = sqlite3.connect(backup)
    conn.backup(bk)
    bk.close()
    print(f'Backup written: {backup}')

    all_targets = []  # (label, repo_dir, name)
    for up_sub, upload_dir, repo_dir, label, jpgs, pdfs, new, changed in plans:
        repo_dir.mkdir(parents=True, exist_ok=True)
        for name in new + changed:
            shutil.copy2(upload_dir / name, repo_dir / name)
        for p in pdfs:
            shutil.copy2(p, repo_dir / p.name)
        taken = set()
        rendered = []
        for p in pdfs:
            rendered += render_pdf(upload_dir / p.name, repo_dir, taken)
        print(f'[{up_sub}] copied {len(new) + len(changed)} JPEGs, {len(pdfs)} PDFs, rendered {len(rendered)} pages')
        for name in sorted(set(new) | set(changed) | set(rendered)):
            all_targets.append((label, repo_dir, name))

    # every JPEG in these repo folders must have a row, even if it was not touched by this upload
    seen = {(lbl, n) for lbl, _, n in all_targets}
    for _, _, repo_dir, label, *_ in plans:
        for f in sorted(repo_dir.glob('*.jpg')):
            if (label, f.name) in seen:
                continue
            if conn.execute('SELECT 1 FROM articles WHERE folder_name = ? AND file_name = ?', (label, f.name)).fetchone():
                continue
            all_targets.append((label, repo_dir, f.name))
            seen.add((label, f.name))
            print(f'   adding missing row: {label} / {f.name}')

    existing = {}
    for label, repo_dir, name in all_targets:
        row = conn.execute('SELECT id FROM articles WHERE folder_name = ? AND file_name = ?', (label, name)).fetchone()
        existing[(label, name)] = row[0] if row else None

    def safe_process(item):
        label, repo_dir, name = item
        rel = (repo_dir / name).as_posix()
        last = None
        for _ in range(3):
            try:
                return item, m.process((existing[(label, name)] or 0, label, name, rel)), None
            except Exception as e:
                last = str(e)
                time.sleep(2)
        return item, None, last

    with ThreadPoolExecutor(4) as ex:
        outcomes = list(ex.map(safe_process, all_targets))

    cur = conn.cursor()
    cur.execute('SELECT COALESCE(MAX(id), 0) FROM articles')
    next_id = cur.fetchone()[0] + 1
    created = updated = 0
    failed = []
    for (label, repo_dir, name), res, err in outcomes:
        if res is None:
            failed.append((label, name, err))
            continue
        row_id = existing[(label, name)]
        if row_id is not None:
            cur.execute('UPDATE articles SET parsed_text = ?, image_rotation = ? WHERE id = ?',
                        (res['text'], res['angle'], row_id))
            updated += 1
        else:
            cur.execute(
                'INSERT INTO articles (id, file_name, folder_name, file_path, parsed_text, image_rotation) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (next_id, name, label, (repo_dir / name).as_posix(), res['text'], res['angle']))
            next_id += 1
            created += 1
    conn.commit()
    conn.close()
    print(f'Database: {created} rows created, {updated} updated, of {len(all_targets)} targets.')
    if failed:
        print(f'FAILED (not updated, re-run to retry): {failed}')


if __name__ == '__main__':
    main()
