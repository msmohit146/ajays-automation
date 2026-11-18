#!/usr/bin/env python3
"""Merge the re-uploaded 1998 folder into the repo's 1998 folder, keeping every scan.

- JPEGs in the upload that are new, or whose content changed, are copied into the
  repo's [SCANS] 1998 folder. Repo files that are not in the upload are kept.
- Each PDF is rendered page by page to JPEG (200 dpi): <stem>.jpg for one-page PDFs,
  <stem>_p<N>.jpg for multi-page ones. If that name already exists in the repo folder,
  the page is written as <stem>_pdf.jpg (or _pdf_p<N>.jpg) so no existing scan is overwritten.
  The PDFs themselves are copied as well.
- Database: every new or changed JPEG/rendered page gets AI angle detection + OCR
  (column-aware prompt). Existing rows are updated, missing rows are created.
  Unchanged rows are left alone.

Usage:
    python sync_1998_upload.py <upload_folder>            # dry run
    python sync_1998_upload.py <upload_folder> --run
"""
import hashlib
import shutil
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pymupdf as fitz  # PyMuPDF

import reocr_imported_with_ai as m

FOLDER_LABEL = '1998- Newest @end'
REPO_SUBDIR = Path('images') / '[SCANS]_ Ajay Srinivisan_ 14th August' / FOLDER_LABEL
DB_PATH = Path('archive.db')
DPI = 200

m.OCR_PROMPT = ("Transcribe all the text on this newspaper/magazine scan. The page may have several columns: "
                "read each column top to bottom, one column at a time, left to right. Keep headlines, bylines, captions and "
                "boxed text separate from the body columns. Never merge or interleave lines from different columns. "
                "Output only the transcription, with paragraph breaks.")


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def repo_oids():
    """sha256 (from the LFS pointer) of every file under the repo's 1998 folder on origin/main."""
    prefix = REPO_SUBDIR.as_posix() + '/'
    ls = subprocess.run(['git', 'ls-tree', '-r', 'origin/main', '--', prefix],
                        capture_output=True, text=True).stdout.splitlines()
    out = {}
    for line in ls:
        meta, path = line.split('\t', 1)
        ptr = subprocess.run(['git', 'cat-file', '-p', meta.split()[2]], capture_output=True, text=True).stdout
        oid = [l.split(':', 1)[1] for l in ptr.splitlines() if l.startswith('oid sha256:')]
        if oid:
            out[Path(path).name] = oid[0]
    return out


def render_pdf(pdf, dest_dir, taken):
    """Render each page to JPEG; returns the created file names. `taken` is updated with every name used."""
    names = []
    doc = fitz.open(pdf)
    stem = pdf.stem
    n_pages = len(doc)
    for i, page in enumerate(doc, 1):
        base = stem if n_pages == 1 else f'{stem}_p{i}'
        name = f'{base}.jpg'
        if name in taken or (dest_dir / name).exists():
            name = f'{base}_pdf.jpg' if n_pages == 1 else f'{stem}_pdf_p{i}.jpg'
        pix = page.get_pixmap(dpi=DPI, colorspace=fitz.csRGB)
        pix.save(dest_dir / name, jpg_quality=92)
        taken.add(name)
        names.append(name)
    doc.close()
    return names


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    upload = Path(sys.argv[1])
    run = '--run' in sys.argv

    jpgs = sorted(p for p in upload.iterdir() if p.suffix.lower() == '.jpg')
    pdfs = sorted(p for p in upload.iterdir() if p.suffix.lower() == '.pdf')
    old = repo_oids()
    new_names, changed_names, same_names = [], [], []
    for j in jpgs:
        if j.name not in old:
            new_names.append(j.name)
        elif old[j.name] != sha256(j):
            changed_names.append(j.name)
        else:
            same_names.append(j.name)
    upload_names = {p.name for p in jpgs} | {p.name for p in pdfs}
    kept = sorted(set(old) - upload_names)
    print(f'Upload: {len(jpgs)} JPEG, {len(pdfs)} PDF')
    print(f'JPEGs: new={len(new_names)}, changed={len(changed_names)}, identical={len(same_names)}')
    print(f'Repo files not in upload (kept): {len(kept)} {kept}')

    if not run:
        print('Dry run only. Re-run with --run.')
        return

    dest = REPO_SUBDIR
    dest.mkdir(parents=True, exist_ok=True)

    # 1. copy new + changed JPEGs and all PDFs
    for name in new_names + changed_names:
        shutil.copy2(upload / name, dest / name)
    for p in pdfs:
        shutil.copy2(p, dest / p.name)

    # 2. render PDF pages without overwriting existing files
    taken = set()
    rendered = []
    for p in pdfs:
        rendered += render_pdf(p, dest, taken)
    print(f'Rendered {len(rendered)} PDF pages')

    # 3. database
    conn = sqlite3.connect(DB_PATH)
    backup = Path(f'archive_before_1998_sync_{datetime.now():%Y%m%d_%H%M%S}.db')
    bk = sqlite3.connect(backup)
    conn.backup(bk)
    bk.close()
    print(f'Backup written: {backup}')

    existing = {r[0]: r[1] for r in conn.execute(
        'SELECT file_name, id FROM articles WHERE folder_name = ?', (FOLDER_LABEL,))}
    targets = sorted(set(new_names) | set(changed_names) | set(rendered))
    rel_of = lambda name: (REPO_SUBDIR / name).as_posix()

    def safe_process(name):
        try:
            return name, m.process((existing.get(name) or 0, FOLDER_LABEL, name, rel_of(name)))
        except Exception as e:
            return name, {'error': str(e)}

    with ThreadPoolExecutor(4) as ex:
        all_results = list(ex.map(safe_process, targets))
    results = [(n, r) for n, r in all_results if 'error' not in r]
    errors = [(n, r['error']) for n, r in all_results if 'error' in r]

    cur = conn.cursor()
    cur.execute('SELECT COALESCE(MAX(id), 0) FROM articles')
    next_id = cur.fetchone()[0] + 1
    created = updated = 0
    for name, res in results:
        if name in existing:
            cur.execute('UPDATE articles SET parsed_text = ?, image_rotation = ? WHERE id = ?',
                        (res['text'], res['angle'], existing[name]))
            updated += 1
        else:
            cur.execute(
                'INSERT INTO articles (id, file_name, folder_name, file_path, parsed_text, image_rotation) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (next_id, name, FOLDER_LABEL, rel_of(name), res['text'], res['angle']))
            next_id += 1
            created += 1
    conn.commit()
    conn.close()
    print(f'Database: {created} rows created, {updated} rows updated. Targets: {len(targets)}.')
    if errors:
        print(f'FAILED (not updated, re-run to retry): {errors}')


if __name__ == '__main__':
    main()
