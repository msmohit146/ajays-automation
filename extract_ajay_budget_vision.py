#!/usr/bin/env python3
"""
Extract only Ajay Srinivasan's budget commentary from article 129.
Remove currency/trading data tables.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")

def extract_ajay_commentary(article_id):
    """Extract only Ajay's budget vision commentary"""
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

    # Find where Ajay's commentary ends - look for the "Budget sees vision" heading
    # which marks the start of the data tables
    end_marker = "## Budget sees vision for"

    if end_marker not in full_text:
        print("ERROR: End marker not found")
        conn.close()
        return False

    end_idx = full_text.find(end_marker)

    # Extract from beginning to just before the data tables
    ajay_text = full_text[:end_idx].strip()

    print(f"OK: Extracted Ajay's commentary")
    print(f"   Original text: {len(full_text)} characters")
    print(f"   Ajay's commentary: {len(ajay_text)} characters")
    print(f"   Removed: {len(full_text) - len(ajay_text)} characters (trading data)")

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
    print(f"   Now contains only Ajay's budget vision commentary")

    return True

if __name__ == "__main__":
    success = extract_ajay_commentary(129)
    exit(0 if success else 1)
