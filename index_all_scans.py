import argparse
import hashlib
import os
import pathlib
import re
import sqlite3
import subprocess
import tempfile

import fitz
import pytesseract
from PIL import Image, ImageOps

BASE_DIR = pathlib.Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "archive.db"
IMAGE_ROOT = BASE_DIR / "images"
TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
PDF_EXTENSIONS = {".pdf"}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def image_ocr(path):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        return clean_text(
            pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6",
            )
        )


def pdf_text(path):
    output = []
    with fitz.open(path) as document:
        for page_number, page in enumerate(document, 1):
            page_text = clean_text(page.get_text("text"))
            output.append(f"[PDF page {page_number}]\n{page_text}")
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temporary:
                image_path = pathlib.Path(temporary.name)
            try:
                pixmap.save(image_path)
                with Image.open(image_path) as image:
                    ocr_text = clean_text(
                        pytesseract.image_to_string(
                            ImageOps.exif_transpose(image),
                            lang="eng",
                            config="--psm 6",
                        )
                    )
                if ocr_text:
                    output.append(f"[OCR page {page_number}]\n{ocr_text}")
            finally:
                image_path.unlink(missing_ok=True)
    return clean_text("\n\n".join(output))


def discover_files():
    files = []
    for path in IMAGE_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS | PDF_EXTENSIONS:
            continue
        relative = path.relative_to(BASE_DIR).as_posix()
        files.append((path, relative))
    return sorted(files, key=lambda item: item[1].casefold())


def main():
    parser = argparse.ArgumentParser(description="Index every scan image and PDF recursively.")
    parser.add_argument("--apply", action="store_true", help="Write missing files to archive.db")
    parser.add_argument("--dry-run", action="store_true", help="Only print the files that would be added")
    parser.add_argument("--no-ocr", action="store_true", help="Add files with empty OCR text instead of invoking OCR")
    args = parser.parse_args()
    if args.dry_run and args.apply:
        parser.error("Use either --dry-run or --apply, not both")

    files = discover_files()
    with sqlite3.connect(DB_PATH, timeout=60) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                folder_name TEXT,
                file_path TEXT,
                parsed_text TEXT,
                raw_ocr_text TEXT,
                image_rotation INTEGER NOT NULL DEFAULT 0
            )"""
        )
        existing_paths = {
            row[0].casefold(): row[1]
            for row in connection.execute("SELECT file_path, id FROM articles")
        }
        existing_hashes = {
            row[0]: row[1]
            for row in connection.execute("SELECT file_path, id FROM articles")
        }
        candidates = []
        for path, relative in files:
            normalized_path = relative.casefold()
            if normalized_path in existing_paths:
                continue
            if path.suffix.lower() in IMAGE_EXTENSIONS:
                candidates.append((path, relative, "image"))
            else:
                candidates.append((path, relative, "pdf"))

        print(f"Discovered {len(files)} files; already indexed {len(files) - len(candidates)}; missing {len(candidates)}")
        print(f"Missing image files: {sum(kind == 'image' for _, _, kind in candidates)}")
        print(f"Missing PDF files: {sum(kind == 'pdf' for _, _, kind in candidates)}")

        if args.dry_run or not args.apply:
            for path, relative, kind in candidates[:20]:
                print(f"WOULD_ADD {kind}: {relative}")
            if len(candidates) > 20:
                print(f"... {len(candidates) - 20} more files omitted from preview")
            return

        imported = 0
        failed = 0
        for path, relative, kind in candidates:
            if args.no_ocr:
                text = ""
            else:
                try:
                    if kind == "image":
                        text = image_ocr(path)
                    else:
                        text = pdf_text(path)
                except Exception as exc:
                    failed += 1
                    text = ""
                    print(f"FAILED {relative}: {type(exc).__name__}: {exc}", flush=True)

            file_name = path.name
            folder_name = path.parent.name
            connection.execute(
                """INSERT INTO articles
                   (file_name, folder_name, file_path, parsed_text, raw_ocr_text, image_rotation)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (file_name, folder_name, relative, text, text),
            )
            connection.commit()
            imported += 1
            if imported % 50 == 0:
                print(f"Imported {imported}/{len(candidates)} files", flush=True)

        print(f"Imported {imported} files; failed {failed}; total database rows {connection.execute('SELECT COUNT(*) FROM articles').fetchone()[0]}")


if __name__ == "__main__":
    main()
