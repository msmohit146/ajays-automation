#!/usr/bin/env python3
import sqlite3
import os
from pathlib import Path

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, "archive.db")
IMAGE_DIR = os.path.join(PROJECT_DIR, "images")
SCAN_MIRROR = "[SCANS]_ Ajay Srinivisan_ 14th August"

def resolve_scan_path(file_path):
    """Resolve the stored path or its matching path in the archive mirror."""
    if not file_path:
        return None

    normalized_file_path = file_path.replace("\\", "/")

    exact_path = os.path.join(PROJECT_DIR, normalized_file_path)
    exact_path = os.path.normpath(exact_path)
    if os.path.isfile(exact_path):
        return exact_path

    relative_path = normalized_file_path.replace("\\", "/")
    if relative_path.startswith("images/"):
        relative_path = relative_path[7:]

    mirror_prefix = f"{SCAN_MIRROR}/"
    if relative_path == ".." or relative_path.startswith(".."):
        return None

    if relative_path.lower().startswith("[scans]_ ajay srinivisan_ 14th august/"):
        alternate_relative = relative_path[len(mirror_prefix):]
    else:
        alternate_relative = f"{mirror_prefix}{relative_path}"

    alternate_path = os.path.join(IMAGE_DIR, *alternate_relative.split("/"))
    alternate_path = os.path.normpath(alternate_path)
    return alternate_path if os.path.isfile(alternate_path) else None


conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT id, file_name, file_path FROM articles WHERE id BETWEEN 2361 AND 2373")
results = cursor.fetchall()
conn.close()

print(f"PROJECT_DIR: {PROJECT_DIR}")
print(f"IMAGE_DIR: {IMAGE_DIR}\n")
print(f"Testing {len(results)} articles:\n")

for article_id, file_name, file_path in results:
    resolved = resolve_scan_path(file_path)
    status = "✓ FOUND" if resolved else "✗ NOT FOUND"
    print(f"ID {article_id}: {status}")
    print(f"  DB path: {file_path}")
    if resolved:
        print(f"  Resolved: {resolved}")
        exists = os.path.isfile(resolved)
        print(f"  File exists: {exists}")
    else:
        print(f"  Resolved: None")
        # Debug why it wasn't found
        test_path = os.path.join(PROJECT_DIR, file_path)
        print(f"  Direct join attempt: {test_path}")
        print(f"  Direct join exists: {os.path.isfile(test_path)}")
    print()
