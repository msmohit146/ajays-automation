import pathlib
import re
import sys
import tempfile

import fitz
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
ROOT = pathlib.Path.cwd() / "images"
SEARCH_WORDS = ("money mint spinner", "money mint", "mint spinner", "money minting")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
PDF_EXTENSIONS = {".pdf"}


def normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def contains_match(text):
    normalized = normalize(text)
    return [term for term in SEARCH_WORDS if term in normalized]


def scan_image(path):
    try:
        with Image.open(path) as image:
            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6",
            )
        return text, contains_match(text)
    except Exception as exc:
        return "", [f"ERROR:{type(exc).__name__}:{exc}"]


def scan_pdf(path):
    try:
        document = fitz.open(path)
        pieces = []
        for page_number in range(len(document)):
            page = document[page_number]
            page_text = page.get_text("text")
            pieces.append(f"[PDF_PAGE {page_number + 1}] {page_text}")
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temporary:
                image_path = temporary.name
            try:
                pixmap.save(image_path)
                with Image.open(image_path) as image:
                    ocr_text = pytesseract.image_to_string(image, lang="eng", config="--psm 6")
                pieces.append(f"[PDF_OCR_PAGE {page_number + 1}] {ocr_text}")
            finally:
                pathlib.Path(image_path).unlink(missing_ok=True)
        return "\n".join(pieces), contains_match("\n".join(pieces))
    except Exception as exc:
        return "", [f"ERROR:{type(exc).__name__}:{exc}"]


matches = []
failed = []
images = sorted(
    path
    for path in ROOT.rglob("*")
    if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    and "\.venv" not in path.parts
    and "ocr_env" not in path.parts
)
pdfs = sorted(
    path
    for path in ROOT.rglob("*")
    if path.is_file() and path.suffix.lower() in PDF_EXTENSIONS
    and "\.venv" not in path.parts
    and "ocr_env" not in path.parts
)

print(f"FILES=images:{len(images)} pdfs:{len(pdfs)}", flush=True)
for path in images:
    text, found = scan_image(path)
    if found and not any(item.startswith("ERROR:") for item in found):
        matches.append((str(path.relative_to(ROOT)), "IMAGE", found, text[:1000]))
    elif any(item.startswith("ERROR:") for item in found):
        failed.append((str(path.relative_to(ROOT)), "IMAGE", found[0]))

for path in pdfs:
    text, found = scan_pdf(path)
    if found and not any(item.startswith("ERROR:") for item in found):
        matches.append((str(path.relative_to(ROOT)), "PDF", found, text[:2000]))
    elif any(item.startswith("ERROR:") for item in found):
        failed.append((str(path.relative_to(ROOT)), "PDF", found[0]))

print(f"MATCHES={len(matches)} FAILED={len(failed)}", flush=True)
for match in matches:
    print("MATCH", match[0], match[1], match[2], flush=True)
for failure in failed:
    print("FAILED", failure, flush=True)

sys.exit(0 if not failed else 1)
