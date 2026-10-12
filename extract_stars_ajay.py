#!/usr/bin/env python3
"""
Extract only Ajay Srinivasan's profile from Stars 2000 article.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")

def extract_ajay_profile(article_id):
    """Extract only Ajay Srinivasan's profile from a multi-person article"""
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

    # Find Ajay's section start
    start_marker = "Ajay Srinivasan (36)"
    if start_marker not in full_text:
        print("ERROR: Ajay Srinivasan profile not found in this article")
        conn.close()
        return False

    start_idx = full_text.find(start_marker)

    # Find where next person's profile starts (Shridhar Subramaniam)
    end_marker = "Shridhar Subramaniam"
    end_idx = full_text.find(end_marker, start_idx)

    if end_idx > start_idx:
        ajay_text = full_text[start_idx:end_idx].strip()
    else:
        ajay_text = full_text[start_idx:].strip()

    print(f"OK: Extracted Ajay's profile")
    print(f"   Original text: {len(full_text)} characters")
    print(f"   Ajay's profile: {len(ajay_text)} characters")
    print(f"   Removed: {len(full_text) - len(ajay_text)} characters")

    # Show preview (safe ASCII only)
    print(f"\nPreview of extracted profile:")
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
    print(f"   Now contains only Ajay Srinivasan's profile")

    return True

if __name__ == "__main__":
    # Extract Ajay's profile from article 1981
    success = extract_ajay_profile(1981)
    exit(0 if success else 1)
