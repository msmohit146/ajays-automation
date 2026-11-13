#!/usr/bin/env python3
"""Re-process the scans added by import_missing_all_folders.py using the AI for
both orientation and OCR.

For each newly imported row:
  1. Ask the model how many degrees the scan must be rotated CLOCKWISE to be upright
     (0, 90, 180, 270). The scan is first EXIF-transposed, same as app.py does.
  2. Store that value in image_rotation. app.py rotates by -image_rotation (clockwise),
     so the stored value and the display agree.
  3. Rotate the image by that amount and send the corrected image to the model for OCR.
  4. Write parsed_text and image_rotation to the row.

Rows are identified as those not present in the pre-import backup.

Usage:
    python reocr_imported_with_ai.py            # dry run: list rows
    python reocr_imported_with_ai.py --run      # back up DB, process, update, save report
"""
import base64
import concurrent.futures as cf
import io
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps

load_dotenv()

from anthropic import Anthropic  # noqa: E402

DB_PATH = Path('archive.db')
PRE_IMPORT_BACKUP = Path('archive_before_missing_import_20261113_170159.db')
MODEL = 'claude-sonnet-5-5'
WORKERS = 4
REPORT_PATH = Path(f'reocr_report_{datetime.now():%Y%m%d_%H%M%S}.json')
OCR_PROMPT = 'Extract all text from this image. Provide clean, readable text.'
ANGLE_PROMPT = (
    'This is a scanned newspaper/magazine page. Decide how many degrees it must be rotated '
    'CLOCKWISE to be upright and readable.\n'
    'Reply with the number on the first line (0, 90, 180 or 270), then one short sentence of reason on the second line.'
)

client = Anthropic()


def load_upright_base(path):
    """Open the scan with EXIF orientation applied, as app.py does."""
    with Image.open(path) as src:
        return ImageOps.exif_transpose(src).convert('RGB')


def to_b64(img, max_side=None, quality=92):
    if max_side and max(img.size) > max_side:
        img = img.copy()
        img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    return base64.standard_b64encode(buf.getvalue()).decode('utf-8')


def ask_model(content_text, image_b64, max_tokens):
    msg = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': image_b64}},
                {'type': 'text', 'text': content_text},
            ],
        }],
    )
    return ''.join(b.text for b in msg.content if hasattr(b, 'text')).strip()


def detect_angle(img):
    reply = ask_model(ANGLE_PROMPT, to_b64(img, max_side=1600, quality=85), max_tokens=300)
    m = re.search(r'\b(0|90|180|270)\b', reply.split('\n')[0]) or re.search(r'\b(0|90|180|270)\b', reply)
    if not m:
        raise ValueError(f'unparseable angle reply: {reply[:120]!r}')
    return int(m.group(1))


def rotate_clockwise(img, degrees):
    if not degrees:
        return img
    return img.rotate(-degrees, expand=True, resample=Image.Resampling.BICUBIC)


def process(row):
    row_id, folder, name, file_path = row
    img = load_upright_base(file_path)
    angle = detect_angle(img)
    corrected = rotate_clockwise(img, angle)
    text = ask_model(OCR_PROMPT, to_b64(corrected), max_tokens=2000)
    return {'id': row_id, 'folder': folder, 'file': name, 'angle': angle,
            'text': text or '[No readable text found]'}


def target_rows(conn):
    old = sqlite3.connect(f'file:{PRE_IMPORT_BACKUP}?mode=ro', uri=True)
    old_keys = set(old.execute('SELECT folder_name, file_name FROM articles').fetchall())
    old.close()
    rows = conn.execute('SELECT id, folder_name, file_name, file_path FROM articles ORDER BY id').fetchall()
    return [r for r in rows if (r[1], r[2]) not in old_keys]


def main():
    run = '--run' in sys.argv
    conn = sqlite3.connect(DB_PATH)
    rows = target_rows(conn)
    print(f'Rows to re-process: {len(rows)}')

    if not run:
        print('Dry run only. Re-run with --run to back up, call the AI, and update rows.')
        conn.close()
        return

    backup = Path(f'archive_before_reocr_{datetime.now():%Y%m%d_%H%M%S}.db')
    bk = sqlite3.connect(backup)
    conn.backup(bk)
    bk.close()
    print(f'Backup written: {backup}')

    results, failed = [], []
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(process, r): r for r in rows}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            r = futs[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                failed.append({'id': r[0], 'file': r[2], 'error': str(e)})
            if i % 10 == 0 or i == len(futs):
                print(f'  processed {i}/{len(futs)}')

    cur = conn.cursor()
    for res in results:
        cur.execute('UPDATE articles SET parsed_text = ?, image_rotation = ? WHERE id = ?',
                    (res['text'], res['angle'], res['id']))
    conn.commit()
    conn.close()

    angles = {}
    for res in results:
        angles[res['angle']] = angles.get(res['angle'], 0) + 1
    REPORT_PATH.write_text(json.dumps({
        'backup': str(backup),
        'rows': len(rows),
        'updated': len(results),
        'angle_counts': angles,
        'failed': failed,
        'results': results,
    }, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Updated {len(results)} rows. Angles: {angles}. Failed: {len(failed)}. Report: {REPORT_PATH}')


if __name__ == '__main__':
    main()
