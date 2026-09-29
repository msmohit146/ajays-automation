import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

import easyocr
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "archive.db")
ROOT_DIR = os.path.join(BASE_DIR, "images")
TESSERACT_EXE = (
    os.environ.get("TESSERACT_CMD")
    or shutil.which("tesseract")
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")

print("Starting resumable OCR indexing for all image folders...", flush=True)
try:
    reader = easyocr.Reader(["en"], gpu=True, verbose=False)
    print("EasyOCR loaded with GPU", flush=True)
except Exception:
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    print("EasyOCR loaded with CPU", flush=True)


def detect_page_rotation(image):
    """Return Tesseract's orientation correction and confidence."""
    if not os.path.isfile(TESSERACT_EXE):
        return 0, 0.0

    with tempfile.TemporaryDirectory() as temp_dir:
        orientation_path = os.path.join(temp_dir, "orientation.png")
        image.save(orientation_path)
        result = subprocess.run(
            [TESSERACT_EXE, orientation_path, "stdout", "-l", "osd", "--psm", "0"],
            capture_output=True,
            timeout=30,
        )

    output = result.stdout.decode("utf-8", errors="replace")
    rotation_match = re.search(r"Rotate:\s*(90|180|270)", output)
    confidence_match = re.search(r"Orientation confidence:\s*([0-9.]+)", output)
    rotation = int(rotation_match.group(1)) if rotation_match else 0
    confidence = float(confidence_match.group(1)) if confidence_match else 0.0
    return rotation, confidence


def preprocess_image(image_path):
    """Apply EXIF and confidently detected pixel rotation before OCR."""
    try:
        with Image.open(image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")

        if os.path.isfile(TESSERACT_EXE):
            try:
                rotation, confidence = detect_page_rotation(image)
                if rotation and confidence >= 5.0:
                    image = image.rotate(-rotation, expand=True)
            except Exception as error:
                print(f"Orientation detection failed for {image_path}: {error}", flush=True)

        image = ImageEnhance.Contrast(image).enhance(1.8)
        image = ImageEnhance.Brightness(image).enhance(1.15)
        image = ImageEnhance.Sharpness(image).enhance(1.2)
        return image
    except Exception as error:
        print(f"Image preprocessing failed for {image_path}: {error}", flush=True)
        return None


def is_usable_text(text):
    alphanumeric = re.findall(r"[A-Za-z0-9]", text or "")
    if len(alphanumeric) < 20:
        return False
    letter_ratio = sum(character.isalpha() for character in alphanumeric) / len(alphanumeric)
    return letter_ratio >= 0.5


def extract_text_tesseract(image_path):
    if not os.path.isfile(TESSERACT_EXE):
        return ""
    try:
        with Image.open(image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        with tempfile.TemporaryDirectory() as temp_dir:
            normalized_path = os.path.join(temp_dir, "scan.png")
            image.save(normalized_path)
            result = subprocess.run(
                [TESSERACT_EXE, normalized_path, "stdout", "-l", "eng", "--psm", "1"],
                capture_output=True,
                check=True,
                timeout=120,
            )
        return result.stdout.decode("utf-8", errors="replace").strip()
    except Exception as error:
        print(f"Tesseract fallback failed for {image_path}: {error}", flush=True)
        return ""


def extract_text_from_image(image_path):
    """OCR the complete normalized page; avoid unreliable whitespace cropping."""
    image = preprocess_image(image_path)
    if image is None:
        return ""

    try:
        results = reader.readtext(np.array(image), detail=1)
    except Exception as error:
        print(f"EasyOCR failed for {image_path}: {error}", flush=True)
        results = []

    sorted_results = sorted(
        results,
        key=lambda result: (
            min(point[1] for point in result[0]),
            min(point[0] for point in result[0]),
        ),
    )
    text = "\n".join(
        detection[1].strip()
        for detection in sorted_results
        if detection[2] > 0.15 and detection[1].strip()
    )

    if not is_usable_text(text):
        fallback_text = extract_text_tesseract(image_path)
        if is_usable_text(fallback_text):
            text = fallback_text
    return text


def process_all_images():
    """Index every scan recursively; skip good rows and refresh bad ones."""
    if not os.path.isdir(ROOT_DIR):
        raise FileNotFoundError(f"Image directory does not exist: {ROOT_DIR}")

    image_list = []
    for root, _, files in os.walk(ROOT_DIR):
        for file_name in files:
            if file_name.lower().endswith(IMAGE_EXTENSIONS):
                image_list.append((os.path.join(root, file_name), file_name, os.path.basename(root)))
    image_list.sort(key=lambda item: item[0].casefold())
    print(f"Found {len(image_list)} scans under {ROOT_DIR}", flush=True)

    refreshed = 0
    skipped = 0
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                folder_name TEXT,
                file_path TEXT,
                parsed_text TEXT
            )"""
        )
        for index, (full_path, file_name, folder_name) in enumerate(image_list, 1):
            relative_path = os.path.relpath(full_path, BASE_DIR).replace("\\", "/")
            existing = conn.execute(
                "SELECT id, parsed_text FROM articles WHERE file_path = ? ORDER BY id LIMIT 1",
                (relative_path,),
            ).fetchone()

            if existing and is_usable_text(existing[1]):
                skipped += 1
                continue

            print(f"[{index}/{len(image_list)}] OCR {relative_path}", flush=True)
            text = extract_text_from_image(full_path)
            if text.strip():
                text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
                text = re.sub(r"\n{3,}", "\n\n", text)
                text = re.sub(r"[ \t]{2,}", " ", text)
                text = re.sub(r"\s+$", "", text, flags=re.MULTILINE).strip()

            if existing:
                conn.execute(
                    "UPDATE articles SET file_name = ?, folder_name = ?, parsed_text = ? WHERE id = ?",
                    (file_name, folder_name, text, existing[0]),
                )
            else:
                conn.execute(
                    """INSERT INTO articles (file_name, folder_name, file_path, parsed_text)
                       VALUES (?, ?, ?, ?)""",
                    (file_name, folder_name, relative_path, text),
                )
            conn.commit()
            refreshed += 1
            if index % 25 == 0:
                print(
                    f"Progress {index}/{len(image_list)}; refreshed={refreshed}; skipped={skipped}",
                    flush=True,
                )

    print(
        f"Archive pass complete: total={len(image_list)}, refreshed={refreshed}, skipped={skipped}",
        flush=True,
    )
    return len(image_list), refreshed, skipped


if __name__ == "__main__":
    process_all_images()
