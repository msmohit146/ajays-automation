import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter

from PIL import Image, ImageOps


def word_similarity(indexed_text, rescanned_text):
    """Compare word content independent of line breaks and reading order."""
    indexed_words = Counter(re.findall(r"[a-z0-9]+", (indexed_text or "").casefold()))
    rescanned_words = Counter(re.findall(r"[a-z0-9]+", (rescanned_text or "").casefold()))
    total_words = sum(indexed_words.values()) + sum(rescanned_words.values())
    if total_words == 0:
        return 1.0
    shared_words = sum((indexed_words & rescanned_words).values())
    return 2 * shared_words / total_words


def extract_text_tesseract(image_path, article_id, tesseract_exe):
    """Re-OCR an EXIF-oriented image without changing the source scan."""
    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")

    with tempfile.TemporaryDirectory() as temp_dir:
        normalized_path = os.path.join(temp_dir, f"scan_{article_id}.png")
        image.save(normalized_path)
        result = subprocess.run(
            [tesseract_exe, normalized_path, "stdout", "-l", "eng", "--psm", "1"],
            capture_output=True,
            check=True,
            timeout=120,
        )
    return result.stdout.decode("utf-8", errors="replace")


def print_console(message):
    encoding = sys.stdout.encoding or "utf-8"
    print(str(message).encode(encoding, errors="replace").decode(encoding, errors="replace"))


def verify_random_samples(sample_size=30, min_similarity=0.15, review_similarity=0.5):
    """Re-OCR random scans and compare their words with the indexed text."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(project_dir, "archive.db")
    if not os.path.exists(db_path):
        print_console("Database not ready yet")
        return False

    tesseract_exe = (
        os.environ.get("TESSERACT_CMD")
        or shutil.which("tesseract")
        or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
    if not os.path.isfile(tesseract_exe):
        print_console(f"Tesseract executable not found: {tesseract_exe}")
        return False

    with sqlite3.connect(db_path, timeout=10) as conn:
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        sample_count = min(max(int(sample_size), 0), total)
        if sample_count == 0:
            print_console("No articles available to verify")
            return False
        samples = conn.execute(
            "SELECT id, file_name, file_path, parsed_text "
            "FROM articles ORDER BY RANDOM() LIMIT ?",
            (sample_count,),
        ).fetchall()

    print_console(f"\nOCR VERIFICATION: Re-reading {sample_count} scans from {total} articles")
    print_console("=" * 60)
    mismatches = []
    reviews = []
    verified = 0

    for article_id, file_name, file_path, indexed_text in samples:
        image_path = file_path if os.path.isabs(file_path) else os.path.join(project_dir, file_path)
        if not os.path.isfile(image_path):
            mismatches.append(f"[CRITICAL] ID {article_id}: Scan not found: {image_path}")
            continue

        try:
            rescanned_text = extract_text_tesseract(image_path, article_id, tesseract_exe)
        except Exception as error:
            mismatches.append(f"[ERROR] ID {article_id}: Could not OCR {file_name}: {error}")
            continue

        similarity = word_similarity(indexed_text, rescanned_text)
        if similarity < min_similarity:
            indexed_preview = " ".join((indexed_text or "").split())[:180]
            rescanned_preview = " ".join(rescanned_text.split())[:180]
            mismatches.append(
                f"[MISMATCH] ID {article_id}: {file_name}, word agreement {similarity:.0%}\n"
                f"  Indexed: {indexed_preview or '[empty]'}\n"
                f"  Re-OCR:  {rescanned_preview or '[no text detected]'}"
            )
            print_console(f"! ID {article_id}: {file_name} ({similarity:.0%} word agreement)")
            continue

        if similarity < review_similarity:
            reviews.append(f"ID {article_id}: {file_name} ({similarity:.0%} word agreement)")
            print_console(f"REVIEW ID {article_id}: {file_name} ({similarity:.0%} word agreement)")
            verified += 1
            continue

        verified += 1
        print_console(f"OK ID {article_id}: {file_name} ({similarity:.0%} word agreement)")

    print_console("\n" + "=" * 60)
    print_console(f"Verified: {verified}/{sample_count}")
    if mismatches:
        print_console("\nISSUES FOUND:")
        for issue in mismatches:
            print_console(issue)
        return False

    if reviews:
        print_console(f"{len(reviews)} low-agreement records need manual review; no definite mismatch found.")
        return True

    print_console("All sampled transcripts agree with a fresh Tesseract pass.")
    return True

if __name__ == "__main__":
    result = verify_random_samples(30)
    if not result:
        exit(1)
