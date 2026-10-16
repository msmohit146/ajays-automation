import pathlib
import sqlite3

base = pathlib.Path.cwd()
baseline = base / 'archive_before_exif_orientation_20261005.db'
image_exts = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp', '.bmp'}
with sqlite3.connect(baseline) as old, sqlite3.connect(base / 'archive.db') as current:
    old_paths = {row[0].casefold() for row in old.execute('SELECT file_path FROM articles')}
    candidates = [
        row
        for row in current.execute(
            'SELECT id, file_name, file_path, parsed_text, raw_ocr_text FROM articles'
        )
        if pathlib.Path(row[2]).suffix.lower() in image_exts
        and row[2].casefold() not in old_paths
    ]
    print(f'baseline_rows={len(old_paths)}')
    print(f'new_image_rows={len(candidates)}')
    print(f'new_image_blank={sum(1 for row in candidates if not (row[3] or "").strip())}')
    print(f'new_image_populated={sum(1 for row in candidates if (row[3] or "").strip())}')
    print(f'new_image_raw_blank={sum(1 for row in candidates if not (row[4] or "").strip())}')
    print('first=' + candidates[0][2] if candidates else 'first=none')
    print('last=' + candidates[-1][2] if candidates else 'last=none')
