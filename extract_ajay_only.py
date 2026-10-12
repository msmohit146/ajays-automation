#!/usr/bin/env python3
"""
Extract only Ajay Srinivasan's commentary from an article.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")

def extract_ajay_text(article_id):
    """Extract only Ajay Srinivasan's text from an article"""
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

    # Find Ajay's section
    if "Ajay Srinivasan" not in full_text:
        print("ERROR: Ajay Srinivasan not found in this article")
        conn.close()
        return False

    # Extract from "Ajay Srinivasan" onwards
    start_idx = full_text.find("Ajay Srinivasan")
    if start_idx == -1:
        print("ERROR: Could not find Ajay Srinivasan section")
        conn.close()
        return False

    ajay_text = full_text[start_idx:].strip()

    print(f"OK: Extracted Ajay's section")
    print(f"   Original text: {len(full_text)} characters")
    print(f"   Ajay's text: {len(ajay_text)} characters")

    # Show preview
    print(f"\nPreview of extracted text:")
    print("-" * 70)
    preview = ajay_text[:400]
    safe_preview = ''.join(c if ord(c) < 128 else '?' for c in preview)
    print(safe_preview)
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
    print(f"   Now contains only Ajay Srinivasan's commentary")

    return True

if __name__ == "__main__":
    # Extract Ajay's text from article 1931
    success = extract_ajay_text(1931)
    exit(0 if success else 1)
