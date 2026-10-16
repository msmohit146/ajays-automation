import hashlib
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path.cwd()
DB = ROOT / "archive.db"


def norm(value):
    value = (value or "").replace("\x00", " ")
    value = re.sub(r"\s+", " ", value).strip().casefold()
    return re.sub(r"[^\w\s]", "", value)


def average_hash(path):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("L")
        image = image.resize((32, 32), Image.Resampling.LANCZOS)
        array = __import__("numpy").asarray(image, dtype="float32")
        array -= array.mean()
        bits = array > 0
        return hashlib.sha256(bits.astype("uint8").tobytes()).hexdigest()


conn = sqlite3.connect(DB)
rows = conn.execute(
    "SELECT id,file_name,folder_name,file_path,parsed_text,raw_ocr_text FROM articles ORDER BY id"
).fetchall()
conn.close()

parsed_groups = defaultdict(list)
raw_groups = defaultdict(list)
for row in rows:
    parsed = norm(row[4])
    raw = norm(row[5])
    if parsed:
        parsed_groups[parsed].append(row)
    if raw:
        raw_groups[raw].append(row)

image_groups = defaultdict(list)
for row in rows:
    path = ROOT / row[3]
    try:
        image_groups[average_hash(path)].append(row)
    except Exception:
        pass

# Report exact normalized OCR groups, independent of image content.
for label, groups in (("PARSED", parsed_groups), ("RAW", raw_groups)):
    duplicates = [group for group in groups.values() if len(group) > 1]
    print(f"{label}_EXACT_GROUPS={len(duplicates)}")
    print(f"{label}_EXACT_RECORDS={sum(len(group) for group in duplicates)}")
    for group in duplicates[:30]:
        print("GROUP", [(r[0], r[1], r[2], r[3]) for r in group])

print(f"IMAGE_HASH_GROUPS={sum(len(group) > 1 for group in image_groups.values())}")
print(f"IMAGE_HASH_RECORDS={sum(len(group) for group in image_groups.values() if len(group) > 1)}")
for group in [group for group in image_groups.values() if len(group) > 1][:50]:
    print("IMAGE_GROUP", [(r[0], r[1], r[2], r[3]) for r in group])

# Find rows with identical normalized OCR and similarly hashed images.
combined = []
for group in parsed_groups.values():
    if len(group) < 2:
        continue
    hashes = {average_hash(ROOT / row[3]) for row in group if (ROOT / row[3]).is_file()}
    if len(hashes) == 1:
        combined.append(group)
for group in raw_groups.values():
    if len(group) < 2:
        continue
    hashes = {average_hash(ROOT / row[3]) for row in group if (ROOT / row[3]).is_file()}
    if len(hashes) == 1:
        combined.append(group)

combined_unique = []
seen_ids = set()
for group in combined:
    group_ids = {row[0] for row in group}
    if not group_ids & seen_ids:
        combined_unique.append(group)
        seen_ids.update(group_ids)

print(f"SAME_OCR_AND_IMAGE_GROUPS={len(combined_unique)}")
for group in combined_unique[:100]:
    print("DUPLICATE", [(r[0], r[1], r[2], r[3]) for r in group])
