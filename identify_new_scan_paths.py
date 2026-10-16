import pathlib
import sqlite3

base = pathlib.Path.cwd()
image_exts = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp', '.bmp'}
all_files = {
    path.relative_to(base).as_posix().casefold(): path
    for path in (base / 'images').rglob('*')
    if path.is_file() and path.suffix.lower() in image_exts
}
with sqlite3.connect(base / 'archive.db') as connection:
    rows = connection.execute(
        "SELECT id, file_name, file_path, parsed_text, raw_ocr_text FROM articles ORDER BY id"
    ).fetchall()
    indexed = {row[2].casefold(): row for row in rows}
    new_paths = [
        (key, path)
        for key, path in all_files.items()
        if key in indexed
        and indexed[key][0] > 868
    ]
    print(f'db_rows={len(rows)}')
    print(f'new_image_paths={len(new_paths)}')
    print(f'new_image_blank={sum(1 for _, row in ((key, indexed[key]) for key, _ in new_paths) if row[3] is None or not row[3].strip())}')
    print(f'new_image_populated={sum(1 for _, row in ((key, indexed[key]) for key, _ in new_paths) if row[3] and row[3].strip())}')
    print('first=' + str(new_paths[0][0]) if new_paths else 'first=none')
    print('last=' + str(new_paths[-1][0]) if new_paths else 'last=none')
