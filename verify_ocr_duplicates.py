import hashlib
import re
import sqlite3
import subprocess
from collections import defaultdict
from pathlib import Path

root = Path.cwd()
local_db = root / "archive.db"
remote_db = root / "archive_remote_check.db"


def normalize(text):
    text = (text or "").replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text


def load(path):
    conn = sqlite3.connect(path)
    rows = conn.execute(
        "SELECT id,file_name,folder_name,file_path,parsed_text,raw_ocr_text FROM articles"
    ).fetchall()
    conn.close()
    return rows


def print_groups(label, rows):
    grouped = defaultdict(list)
    for row in rows:
        key = normalize(row[4] or row[5])
        if key:
            grouped[key].append(row)
    groups = [group for group in grouped.values() if len(group) > 1]
    print(f"{label}_rows={len(rows)}")
    print(f"{label}_exact_text_groups={len(groups)}")
    print(f"{label}_exact_text_records={sum(len(group) for group in groups)}")
    for group in groups[:10]:
        print("GROUP", [(r[0], r[1], r[2], r[3]) for r in group])


local_rows = load(local_db)
print_groups("LOCAL", local_rows)

subprocess.run(
    ["git", "show", "origin/main:archive.db"],
    stdout=remote_db.open("wb"),
    check=True,
)
remote_rows = load(remote_db)
print_groups("REMOTE", remote_rows)

# Compare exact normalized OCR strings across local records and report their IDs/paths.
local_texts = defaultdict(list)
for row in local_rows:
    key = normalize(row[4] or row[5])
    if key:
        local_texts[key].append(row)

for key, group in local_texts.items():
    if len(group) > 1:
        print("LOCAL_DUPLICATE_TEXT", [(r[0], r[1], r[2], r[3]) for r in group])
        print("LOCAL_TEXT", repr(key[:500]))

remote_texts = defaultdict(list)
for row in remote_rows:
    key = normalize(row[4] or row[5])
    if key:
        remote_texts[key].append(row)

for key, group in remote_texts.items():
    if len(group) > 1:
        print("REMOTE_DUPLICATE_TEXT", [(r[0], r[1], r[2], r[3]) for r in group])
        print("REMOTE_TEXT", repr(key[:500]))

remote_db.unlink(missing_ok=True)
print("VERIFICATION_COMPLETE")
