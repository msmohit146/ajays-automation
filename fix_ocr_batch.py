#!/usr/bin/env python3
"""
Fix OCR text for multiple articles using Claude's vision.
"""

import sqlite3
import base64
import sys
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path("archive.db")
IMAGES_DIR = Path("images")

def resolve_file_path(file_path):
    if file_path.startswith("images/"):
        full_path = Path(file_path)
    else:
        full_path = IMAGES_DIR / file_path

    if full_path.exists():
        return str(full_path)

    alt_path = IMAGES_DIR / file_path.replace("/", "\\")
    if alt_path.exists():
        return str(alt_path)

    return None

def get_image_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def get_image_media_type(file_path):
    ext = Path(file_path).suffix.lower()
    if ext in ['.jpg', '.jpeg']:
        return "image/jpeg"
    elif ext == '.png':
        return "image/png"
    elif ext == '.gif':
        return "image/gif"
    elif ext == '.webp':
        return "image/webp"
    else:
        return "image/jpeg"

def fix_article(article_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT file_name, file_path, parsed_text FROM articles WHERE id = ?",
        (article_id,)
    )
    result = cursor.fetchone()
    conn.close()

    if not result:
        print(f"ERROR: Article ID {article_id} not found")
        return False

    file_name, file_path, original_text = result

    print(f"Processing: {file_name}")
    print(f"   ID: {article_id}")

    full_path = resolve_file_path(file_path)
    if not full_path:
        print(f"ERROR: File not found")
        return False

    print(f"OK: File found")

    image_base64 = get_image_base64(full_path)
    media_type = get_image_media_type(full_path)

    print("Extracting text with Claude vision...")
    client = Anthropic()
    message = client.messages.create(
        model="claude-opus-5-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": """Please extract ALL text from this image with 100% accuracy.

Instructions:
1. Read every word carefully, including headers, footers, and any text in multiple columns
2. Preserve the structure (paragraphs, line breaks, etc.)
3. Fix any OCR errors to make the text coherent and readable
4. Include all visible text from the entire image
5. Return ONLY the extracted text, no commentary

If this is a document with multiple columns, organize them in reading order (left to right, top to bottom).
If this is a newspaper article with headers/titles, preserve those.

Extracted text:"""
                    }
                ]
            }
        ]
    )

    # Handle both text and thinking blocks
    extracted_text = None
    for block in message.content:
        if hasattr(block, 'text'):
            extracted_text = block.text.strip()
            break

    if not extracted_text:
        print("ERROR: No text content in response")
        return False

    print(f"OK: Extracted {len(extracted_text)} characters")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE articles SET parsed_text = ? WHERE id = ?",
        (extracted_text, article_id)
    )
    conn.commit()
    conn.close()

    print(f"SUCCESS: Updated article ID {article_id}")
    print(f"   Original: {len(original_text) if original_text else 0} characters")
    print(f"   Corrected: {len(extracted_text)} characters")
    print()

    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_ocr_batch.py <article_id> [article_id2] ...")
        sys.exit(1)

    article_ids = [int(id_str) for id_str in sys.argv[1:]]

    successful = 0
    for article_id in article_ids:
        if fix_article(article_id):
            successful += 1

    print(f"\nProcessed {len(article_ids)} articles, {successful} successful")
    sys.exit(0 if successful == len(article_ids) else 1)
