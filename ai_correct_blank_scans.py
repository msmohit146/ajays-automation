import argparse
import sqlite3
import time
from pathlib import Path

from text_alignment_fixer import fix_text_with_image

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "archive.db"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


def main():
    parser = argparse.ArgumentParser(description="Correct newly imported scans using Claude vision")
    parser.add_argument("--resume-id", type=int, default=0, help="Skip rows with IDs at or below this value")
    args = parser.parse_args()

    baseline_path = BASE_DIR / "archive_before_exif_orientation_20261005.db"
    with sqlite3.connect(DB_PATH, timeout=60) as connection, sqlite3.connect(baseline_path) as baseline:
        baseline_paths = {
            row[0].casefold()
            for row in baseline.execute("SELECT file_path FROM articles")
        }
        rows = connection.execute(
            """
            SELECT id, file_name, file_path, parsed_text, raw_ocr_text
            FROM articles
            ORDER BY id
            """
        ).fetchall()
        rows = [
            row
            for row in rows
            if Path(row[2]).suffix.lower() in IMAGE_EXTENSIONS
            and row[2].casefold() not in baseline_paths
            and row[0] > args.resume_id
        ]

        processed = 0
        failed = 0
        for article_id, file_name, relative_path, _, source_text in rows:
            path = relative_path if Path(relative_path).is_absolute() else BASE_DIR / relative_path
            try:
                corrected = fix_text_with_image(file_name, str(path), source_text or "")
                connection.execute(
                    "UPDATE articles SET parsed_text = ?, raw_ocr_text = ? WHERE id = ?",
                    (corrected, source_text or "", article_id),
                )
                connection.commit()
                processed += 1
                print(f"AI_FIXED {processed}/{len(rows)} id={article_id} file={file_name}", flush=True)
            except Exception as exc:
                failed += 1
                print(f"AI_FAILED id={article_id} file={file_name} error={type(exc).__name__}: {exc}", flush=True)
                time.sleep(1)

        print(f"FINAL processed={processed} failed={failed} total={len(rows)}", flush=True)


if __name__ == "__main__":
    main()
