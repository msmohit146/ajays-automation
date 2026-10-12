#!/usr/bin/env python3
"""
Fix OCR text for a single article using Claude's vision capabilities.
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
    """Resolve file path to actual location"""
    # Try direct path first
    if file_path.startswith("images/"):
        full_path = Path(file_path)
    else:
        full_path = IMAGES_DIR / file_path

    if full_path.exists():
        return str(full_path)

    # Try with Windows path separators
    alt_path = IMAGES_DIR / file_path.replace("/", "\\")
    if alt_path.exists():
        return str(alt_path)

    return None

def get_image_base64(image_path):
    """Read image and convert to base64"""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def get_image_media_type(file_path):
    """Get media type based on file extension"""
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
    """Fix OCR text for a single article"""
    # Get article info from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT file_name, file_path, parsed_text FROM articles WHERE id = ?",
        (article_id,)
    )
    result = cursor.fetchone()

    if not result:
        print(f"ERROR: Article ID {article_id} not found")
        return False

    file_name, file_path, original_text = result
    conn.close()

    print(f"Processing: {file_name}")
    print(f"   ID: {article_id}")

    # Resolve file path
    full_path = resolve_file_path(file_path)
    if not full_path:
        print(f"ERROR: File not found: {file_path}")
        return False

    print(f"OK: File found")

    # Read and encode image
    image_base64 = get_image_base64(full_path)
    media_type = get_image_media_type(full_path)

    # Call Claude vision API
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

    # Show preview of corrected text
    print(f"\nPreview of corrected text:")
    print("-" * 70)
    preview = extracted_text[:300]
    print(preview)
    if len(extracted_text) > 300:
        print("...")
    print("-" * 70)

    # Update database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE articles SET parsed_text = ? WHERE id = ?",
        (extracted_text, article_id)
    )
    conn.commit()
    conn.close()

    print(f"\nSUCCESS: Updated article ID {article_id}")
    print(f"   Original: {len(original_text) if original_text else 0} characters")
    print(f"   Corrected: {len(extracted_text)} characters")

    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        article_id = int(sys.argv[1])
    else:
        article_id = 1929  # Default to the jumbled article

    success = fix_article(article_id)
    sys.exit(0 if success else 1)
