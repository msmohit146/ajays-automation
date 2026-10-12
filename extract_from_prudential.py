#!/usr/bin/env python3
"""
Extract from the Prudential ICICI line onwards, removing everything before.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")

def extract_from_line(article_id, search_text):
    """Extract from a specific line onwards"""
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

    # Find the target text
    if search_text not in full_text:
        print(f"ERROR: Target text not found in this article")
        conn.close()
        return False

    start_idx = full_text.find(search_text)

    kept_text = full_text[start_idx:].strip()

    print(f"OK: Extracted from target line")
    print(f"   Original text: {len(full_text)} characters")
    print(f"   Kept text: {len(kept_text)} characters")
    print(f"   Removed: {len(full_text) - len(kept_text)} characters")

    # Show preview
    print(f"\nPreview of kept text:")
    print("-" * 70)
    preview = kept_text[:400]
    safe_preview = ''.join(c if ord(c) < 128 else '?' for c in preview)
    print(safe_preview)
    if len(kept_text) > 400:
        print("...")
    print("-" * 70)

    # Update database
    cursor.execute(
        "UPDATE articles SET parsed_text = ? WHERE id = ?",
        (kept_text, article_id)
    )
    conn.commit()
    conn.close()

    print(f"\nSUCCESS: Updated article ID {article_id}")
    print(f"   Removed all text before the target line")

    return True

if __name__ == "__main__":
    # Extract from the Prudential ICICI line in article 1950
    search_text = "Prudential ICICI is one of the asset management"
    success = extract_from_line(1950, search_text)
    exit(0 if success else 1)
