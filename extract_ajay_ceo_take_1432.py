#!/usr/bin/env python3
"""
Extract only Ajay's CEO Take section from article 1432.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")

def extract_ceo_take(article_id):
    """Extract only the CEO Take section"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT file_name, parsed_text FROM articles WHERE id = ?",
        (article_id,)
    )
    result = cursor.fetchone()

    if not result:
        print(f"ERROR: Article ID {article_id} not found")
        conn.close()
        return False

    file_name, full_text = result

    print(f"Processing: {file_name}")
    print(f"   ID: {article_id}")

    # Find the CEO Take section start
    start_marker = "## CEO Take"
    if start_marker not in full_text:
        print("ERROR: CEO Take section not found")
        conn.close()
        return False

    start_idx = full_text.find(start_marker)

    # Find where CEO Take ends - look for next section
    end_marker = "## Questions Asked"
    end_idx = len(full_text)

    if end_marker in full_text:
        end_idx = full_text.find(end_marker)

    ajay_text = full_text[:end_idx].strip()

    print(f"OK: Extracted CEO Take section")
    print(f"   Original text: {len(full_text)} characters")
    print(f"   CEO Take section: {len(ajay_text)} characters")
    print(f"   Removed: {len(full_text) - len(ajay_text)} characters")

    # Show preview
    print(f"\nPreview of kept text:")
    print("-" * 70)
    preview = ajay_text[:400]
    safe_preview = ''.join(c if ord(c) < 128 else '?' for c in preview)
    print(safe_preview)
    if len(ajay_text) > 400:
        print("...")
    print("-" * 70)

    # Update database
    cursor.execute(
        "UPDATE articles SET parsed_text = ? WHERE id = ?",
        (ajay_text, article_id)
    )
    conn.commit()
    conn.close()

    print(f"\nSUCCESS: Updated article ID {article_id}")
    print(f"   Now contains only the CEO Take section")

    return True

if __name__ == "__main__":
    success = extract_ceo_take(1432)
    exit(0 if success else 1)
