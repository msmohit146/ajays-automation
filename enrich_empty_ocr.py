import pathlib
import re
import sqlite3
import sys
import tempfile

import fitz
import pytesseract
from PIL import Image, ImageOps

from scan_orientation import load_oriented_image

BASE_DIR = pathlib.Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "archive.db"
TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def ocr_image(path):
    with load_oriented_image(path, TESSERACT_EXE) as image:
        return clean_text(
            pytesseract.image_to_string(image, lang="eng", config="--psm 6")
        )


def ocr_pdf(path):
    pieces = []
    with fitz.open(path) as document:
        for page_number, page in enumerate(document, 1):
            page_text = clean_text(page.get_text("text"))
            if page_text:
                pieces.append(f"[PDF page {page_number}]\n{page_text}")
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temporary:
                image_path = pathlib.Path(temporary.name)
            try:
                pixmap.save(image_path)
                with Image.open(image_path) as image:
                    image = ImageOps.exif_transpose(image)
                    ocr_text = clean_text(
                        pytesseract.image_to_string(image, lang="eng", config="--psm 6")
                    )
                if ocr_text:
                    pieces.append(f"[OCR page {page_number}]\n{ocr_text}")
            finally:
                image_path.unlink(missing_ok=True)
    return clean_text("\n\n".join(pieces))


def main():
    with sqlite3.connect(DB_PATH, timeout=60) as connection:
        rows = connection.execute(
            "SELECT id, file_path FROM articles WHERE parsed_text IS NULL OR TRIM(parsed_text) = '' ORDER BY id"
        ).fetchall()
        total = len(rows)
        processed = 0
        failed = 0
        for article_id, relative_path in rows:
            path = BASE_DIR / relative_path
            try:
                if path.suffix.lower() == ".pdf":
                    text = ocr_pdf(path)
                elif path.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}:
                    text = ocr_image(path)
                else:
                    text = ""
                connection.execute(
                    "UPDATE articles SET parsed_text = ?, raw_ocr_text = ? WHERE id = ?",
                    (text, text, article_id),
                )
                connection.commit()
            except Exception as exc:
                failed += 1
                print(f"FAILED id={article_id} path={relative_path} error={type(exc).__name__}: {exc}", flush=True)
                connection.rollback()

            processed += 1
            if processed % 25 == 0 or processed == total:
                print(
                    f"PROGRESS {processed}/{total} processed failed={failed} id={article_id}",
                    flush=True,
                )
        print(f"FINAL processed={processed} failed={failed}", flush=True)


if __name__ == "__main__":
    main()
