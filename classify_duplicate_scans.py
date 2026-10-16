import hashlib
import re
import sqlite3
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path.cwd()
DB = ROOT / "archive.db"


def normalize_text(value):
    value = value or ""
    value = re.sub(r"\s+", " ", value).strip().casefold()
    return re.sub(r"[^\w\s]", "", value)


def fingerprint(path):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("L")
        image = image.resize((32, 32), Image.Resampling.LANCZOS)
        array = np.asarray(image, dtype=np.float32)
        array -= array.mean()
        return hashlib.sha256(array.tobytes()).hexdigest(), float(np.mean(array * array))


conn = sqlite3.connect(DB)
rows = conn.execute(
    "SELECT id,file_name,folder_name,file_path,parsed_text,raw_ocr_text FROM articles ORDER BY id"
).fetchall()
conn.close()

text_groups = defaultdict(list)
for row in rows:
    key = normalize_text(row[4] or row[5])
    if key:
        text_groups[key].append(row)

exact_text_groups = [group for group in text_groups.values() if len(group) > 1]
print(f"rows={len(rows)} exact_ocr_groups={len(exact_text_groups)}")

image_records = []
for row in rows:
    path = ROOT / row[3]
    if not path.is_file():
        continue
    try:
        digest, energy = fingerprint(path)
    except Exception:
        continue
    image_records.append((row, digest, energy, path))

image_groups = defaultdict(list)
for record, digest, energy, path in image_records:
    image_groups[digest].append((record, digest, energy, path))

exact_image_groups = [group for group in image_groups.values() if len(group) > 1]
print(f"exact_image_groups={len(exact_image_groups)} exact_image_rows={sum(len(group) for group in exact_image_groups)}")

# Compare image fingerprints with a stable, low-cost visual similarity metric.
visual_candidates = []
for index, first in enumerate(image_records):
    first_row, first_digest, first_energy, first_path = first
    for second in image_records[index + 1:]:
        second_row, second_digest, second_energy, second_path = second
        if first_row[0] == second_row[0]:
            continue
        first_text = normalize_text(first_row[4] or first_row[5])
        second_text = normalize_text(second_row[4] or second_row[5])
        text_ratio = SequenceMatcher(None, first_text, second_text).ratio()
        if text_ratio < 0.90:
            continue
        first_array = np.asarray(ImageOps.exif_transpose(Image.open(first_path)).convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32)
        second_array = np.asarray(ImageOps.exif_transpose(Image.open(second_path)).convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32)
        first_array -= first_array.mean()
        second_array -= second_array.mean()
        denominator = np.linalg.norm(first_array) * np.linalg.norm(second_array)
        similarity = float(np.dot(first_array.ravel(), second_array.ravel()) / max(denominator, 1e-9))
        if similarity >= 0.88:
            visual_candidates.append((similarity, text_ratio, first_row, second_row))

print(f"visual_similarity_candidates={len(visual_candidates)}")
for similarity, text_ratio, first, second in visual_candidates[:100]:
    print(
        f"SIM={similarity:.4f} TEXT={text_ratio:.4f} "
        f"ID1={first[0]} {first[1]} {first[3]} | "
        f"ID2={second[0]} {second[1]} {second[3]}"
    )
