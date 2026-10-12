#!/usr/bin/env python3
"""
Extract only Ajay Srinivasan's section from an article, removing everything before.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")

def extract_from_ajay_onwards(article_id):
    """Extract from Ajay Srinivasan onwards"""
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

    # Find the --- separator before Ajay
    ajay_idx = full_text.find("Ajay Srinivasan")

    # Look for the --- before Ajay
    before_ajay = full_text[:ajay_idx]
    last_separator = before_ajay.rfind("---")

    if last_separator != -1:
        # Start from after the --- separator
        start_idx = full_text.find("**Ajay Srinivasan**")
        if start_idx == -1:
            start_idx = full_text.find("Ajay Srinivasan")
    else:
        start_idx = full_text.find("Ajay Srinivasan")

    if start_idx == -1:
        print("ERROR: Could not find Ajay Srinivasan section")
        conn.close()
        return False

    ajay_text = full_text[start_idx:].strip()

    print(f"OK: Extracted Ajay's section")
    print(f"   Original text: {len(full_text)} characters")
    print(f"   Kept text: {len(ajay_text)} characters")
    print(f"   Removed: {len(full_text) - len(ajay_text)} characters")

    # Show preview
    print(f"\nPreview of kept text:")
    print("-" * 70)
    preview = ajay_text[:500]
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
    print(f"   Removed all text before Ajay Srinivasan's section")

    return True

if __name__ == "__main__":
    # Extract Ajay's section from article 1933
    success = extract_from_ajay_onwards(1933)
    exit(0 if success else 1)
