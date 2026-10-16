import pathlib
import sqlite3
from datetime import datetime

base = pathlib.Path.cwd()
with sqlite3.connect(base / "archive.db") as connection:
    total = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    max_id = connection.execute("SELECT MAX(id) FROM articles").fetchone()[0]
    image_rows = connection.execute(
        "SELECT id, file_name, file_path, parsed_text, raw_ocr_text FROM articles WHERE file_path LIKE ? ORDER BY id DESC LIMIT 20", ("%.jpg",)
    ).fetchall()
    blank = connection.execute(
        "SELECT COUNT(*) FROM articles WHERE file_path LIKE ? AND (parsed_text IS NULL OR TRIM(parsed_text) = '')", ("%.jpg",)
    ).fetchone()[0]
    ai_done = connection.execute(
        "SELECT COUNT(*) FROM articles WHERE file_path LIKE ? AND raw_ocr_text IS NOT NULL AND parsed_text IS NOT NULL AND TRIM(parsed_text) <> ''", ("%.jpg",)
    ).fetchone()[0]
    print(f"total={total} max_id={max_id} blank_images={blank} populated_images={ai_done}")
    for row in image_rows:
        print(f"id={row[0]} file={row[1]} path={row[2]} parsed_chars={len(row[3] or '')} raw_chars={len(row[4] or '')}")
