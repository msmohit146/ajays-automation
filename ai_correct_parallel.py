import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

from text_alignment_fixer import fix_text_with_image

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "archive.db"
BASELINE_PATH = BASE_DIR / "archive_before_exif_orientation_20261005.db"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


def image_target_rows(connection, baseline_paths):
    rows = connection.execute(
        """
        SELECT id, file_name, file_path, parsed_text, raw_ocr_text
        FROM articles
        ORDER BY id
        """
    ).fetchall()
    return [
        row
        for row in rows
        if Path(row[2]).suffix.lower() in IMAGE_EXTENSIONS
        and row[2].casefold() not in baseline_paths
    ]


def existing_processed_ids(log_path):
    if not log_path.exists():
        return set()
    ids = set()
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.search(r"\bid=(\d+)\b", line)
        if match:
            ids.add(int(match.group(1)))
    return ids


def main():
    parser = argparse.ArgumentParser(description="Process new-image AI corrections in parallel")
    parser.add_argument("--worker", type=int, required=True, choices=(0, 1, 2, 3))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()

    if args.workers != 4 or args.worker not in range(args.workers):
        parser.error("This worker launcher requires --workers 4 and --worker 0 through 3")

    with sqlite3.connect(DB_PATH, timeout=60) as connection, sqlite3.connect(BASELINE_PATH) as baseline:
        baseline_paths = {
            row[0].casefold()
            for row in baseline.execute("SELECT file_path FROM articles")
        }
        rows = image_target_rows(connection, baseline_paths)
        worker_rows = [row for index, row in enumerate(rows) if index % args.workers == args.worker]
        processed_ids = existing_processed_ids(args.log)
        worker_rows = [row for row in worker_rows if row[0] not in processed_ids]

        log_path = args.log or BASE_DIR / f"ai_correct_worker_{args.worker + 1}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")
        processed = 0
        failed = 0

        for article_id, file_name, relative_path, _, source_text in worker_rows:
            path = relative_path if Path(relative_path).is_absolute() else BASE_DIR / relative_path
            try:
                corrected = fix_text_with_image(file_name, str(path), source_text or "")
                connection.execute(
                    "UPDATE articles SET parsed_text = ?, raw_ocr_text = ? WHERE id = ?",
                    (corrected, source_text or "", article_id),
                )
                connection.commit()
                processed += 1
                line = f"AI_FIXED {processed}/{len(worker_rows)} id={article_id} file={file_name}"
                print(line, flush=True)
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except Exception as exc:
                failed += 1
                line = f"AI_FAILED id={article_id} file={file_name} error={type(exc).__name__}: {exc}"
                print(line, flush=True)
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
                time.sleep(1)

        final = f"FINAL worker={args.worker + 1} processed={processed} failed={failed} total={len(worker_rows)}"
        print(final, flush=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(final + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
