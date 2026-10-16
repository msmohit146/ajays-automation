import pathlib
import sqlite3

base = pathlib.Path.cwd()
for backup in sorted(base.glob('archive_pre_ai_*.db')) + sorted(base.glob('archive_before_*.db')):
    try:
        with sqlite3.connect(backup) as c:
            rows = c.execute('SELECT file_path FROM articles').fetchall()
            images = [r[0] for r in rows if r[0].lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp', '.bmp'))]
            print(f'{backup.name}: rows={len(rows)} images={len(images)} max_id={c.execute("SELECT MAX(id) FROM articles").fetchone()[0]}')
    except Exception as exc:
        print(f'{backup.name}: ERROR {exc}')
