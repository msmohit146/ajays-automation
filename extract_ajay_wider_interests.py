#!/usr/bin/env python3
"""
Extract only Ajay Srinivasan's sections from article 1607 - Wider Interests.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")

def extract_ajay_content(article_id):
    """Extract only Ajay Srinivasan's CEO Take and commentary"""
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

    # Find Ajay's first appearance (CEO Take section)
    start_marker = "AJAY SRINIVASAN\n\nREKHA"
    # Find the actual position where Ajay's CEO Take starts
    if "AJAY SRINIVASAN" not in full_text:
        print("ERROR: Ajay's content not found")
        conn.close()
        return False

    # Start from first AJAY SRINIVASAN mention
    start_idx = full_text.find("AJAY SRINIVASAN")

    # Find where to end - look for "Fun Moment" which comes after his commentary
    end_marker = "Fun Moment"
    end_idx = len(full_text)

    if end_marker in full_text:
        end_idx = full_text.find(end_marker)

    ajay_text = full_text[start_idx:end_idx].strip()

    print(f"OK: Extracted Ajay's sections")
    print(f"   Original text: {len(full_text)} characters")
    print(f"   Ajay's content: {len(ajay_text)} characters")
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
    print(f"   Now contains only Ajay Srinivasan's CEO Take and commentary")

    return True

if __name__ == "__main__":
    success = extract_ajay_content(1607)
    exit(0 if success else 1)
