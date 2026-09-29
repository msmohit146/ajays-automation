import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageOps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "archive.db")
ROOT_DIR = os.path.join(BASE_DIR, "images")
TESSERACT_EXE = (
    os.environ.get("TESSERACT_CMD")
    or shutil.which("tesseract")
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
WORKERS = 4


def is_usable_text(text):
    alphanumeric = re.findall(r"[A-Za-z0-9]", text or "")
    if len(alphanumeric) < 100:
        return False
    letter_ratio = sum(character.isalpha() for character in alphanumeric) / len(alphanumeric)
    return letter_ratio >= 0.5


def extract_text_from_image(image_path):
    """OCR with auto-layout, then retry short results on cropped rotations."""
    if not os.path.isfile(TESSERACT_EXE):
        raise FileNotFoundError(f"Tesseract executable not found: {TESSERACT_EXE}")

    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")

    def recognize(source_image, label, page_mode=1):
        with tempfile.TemporaryDirectory() as temp_dir:
            normalized_path = os.path.join(temp_dir, f"{label}.png")
            source_image.save(normalized_path)
            child_environment = os.environ.copy()
            child_environment["OMP_THREAD_LIMIT"] = "1"
            result = subprocess.run(
                [TESSERACT_EXE, normalized_path, "stdout", "-l", "eng", "--psm", str(page_mode)],
                capture_output=True,
                check=True,
                timeout=120,
                env=child_environment,
            )
        return result.stdout.decode("utf-8", errors="replace").strip()

    text = recognize(image, "scan")
    if is_usable_text(text):
        return text

    gray = ImageOps.grayscale(image)
    content_box = gray.point(lambda value: 255 if value < 225 else 0).getbbox()
    if not content_box:
        return text

    left, top, right, bottom = content_box
    padding = 8
    crop_box = (
        max(0, left - padding),
        max(0, top - padding),
        min(image.width, right + padding),
        min(image.height, bottom + padding),
    )
    cropped = image.crop(crop_box)
    cropped_text = recognize(cropped, "cropped")
    if is_usable_text(cropped_text):
        return cropped_text

    best_text = cropped_text if len(cropped_text) > len(text) else text
    best_score = (is_usable_text(best_text), len(re.findall(r"[A-Za-z0-9]", best_text)))

    for angle in (90, 180, 270):
        candidate = cropped.rotate(angle, expand=True)
        candidate_text = recognize(candidate, f"crop_{angle}", page_mode=6)
        candidate_score = (
            is_usable_text(candidate_text),
            len(re.findall(r"[A-Za-z0-9]", candidate_text)),
        )
        if candidate_score > best_score:
            best_text = candidate_text
            best_score = candidate_score
        if is_usable_text(best_text) and best_score[1] >= 300:
            break

    return best_text


def clean_text(text):
    if not text.strip():
        return ""
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r"\s+$", "", text, flags=re.MULTILINE).strip()


def process_all_images():
    """Index every scan recursively; keep good rows and resume by exact path."""
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
    failures = 0
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

        work = []
        for index, (full_path, file_name, folder_name) in enumerate(image_list, 1):
            relative_path = os.path.relpath(full_path, BASE_DIR).replace("\\", "/")
            existing = conn.execute(
                "SELECT id, parsed_text FROM articles WHERE file_path = ? ORDER BY id LIMIT 1",
                (relative_path,),
            ).fetchone()
            if existing and is_usable_text(existing[1]):
                skipped += 1
                continue
            work.append((index, full_path, file_name, folder_name, relative_path, existing))

        print(
            f"OCR queue: {len(work)} scans; already usable: {skipped}; workers: {WORKERS}",
            flush=True,
        )
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            future_items = [
                (item, executor.submit(extract_text_from_image, item[1]))
                for item in work
            ]
            for item, future in future_items:
                index, full_path, file_name, folder_name, relative_path, existing = item
                try:
                    text = clean_text(future.result())
                except Exception as error:
                    failures += 1
                    print(f"OCR failed [{index}/{len(image_list)}] {relative_path}: {error}", flush=True)
                    continue

                if not is_usable_text(text):
                    failures += 1
                    print(f"Low-quality OCR [{index}/{len(image_list)}] {relative_path}", flush=True)

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
                if refreshed % 25 == 0:
                    print(
                        f"Progress: refreshed={refreshed}/{len(work)}; skipped={skipped}; failures={failures}",
                        flush=True,
                    )

    print(
        f"Archive pass complete: total={len(image_list)}, refreshed={refreshed}, "
        f"skipped={skipped}, failures={failures}",
        flush=True,
    )
    return len(image_list), refreshed, skipped, failures


if __name__ == "__main__":
    process_all_images()
