#!/usr/bin/env python3
"""
Re-extract article 2041 image with proper orientation handling using Claude's vision API.
"""

import sqlite3
import os
import base64
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

DB_PATH = Path("archive.db")
PROJECT_DIR = Path(__file__).parent

client = Anthropic()

def get_image_path(folder_name, file_name):
    """Construct path to image file."""
    image_dir = PROJECT_DIR / "images"
    return image_dir / folder_name / file_name

def extract_text_with_vision(image_path):
    """Extract text from image using Claude's vision API."""
    if not image_path.exists():
        print(f"Error: Image file not found: {image_path}")
        return None

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    message = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Please extract all text from this image. The image may be rotated or have orientation issues - extract the text as it should be read normally. Only provide the extracted text without any additional commentary."
                    }
                ],
            }
        ],
    )

    extracted_text = ""
    for block in message.content:
        if hasattr(block, 'text'):
            extracted_text += block.text

    return extracted_text.strip()

def main():
    article_id = 2041

    # Get article info
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT file_name, folder_name, parsed_text FROM articles WHERE id = ?",
        (article_id,)
    )
    result = cursor.fetchone()

    if not result:
        print(f"ERROR: Article {article_id} not found")
        conn.close()
        return False

    file_name, folder_name, old_text = result

    print(f"Processing article {article_id}: {file_name}")
    print(f"Folder: {folder_name}")

    # Get image path
    image_path = get_image_path(folder_name, file_name)
    print(f"Image path: {image_path}")

    if not image_path.exists():
        print(f"ERROR: Image not found")
        conn.close()
        return False

    # Extract text
    print("Extracting text with Claude vision API...")
    new_text = extract_text_with_vision(image_path)

    if not new_text:
        print("ERROR: Failed to extract text")
        conn.close()
        return False

    print(f"Extracted {len(new_text)} characters")

    # Update database with extracted text and set rotation to 0
    cursor.execute(
        "UPDATE articles SET parsed_text = ?, image_rotation = 0 WHERE id = ?",
        (new_text, article_id)
    )
    conn.commit()

    print(f"SUCCESS: Updated article {article_id}")
    print(f"  Old text: {len(old_text)} characters")
    print(f"  New text: {len(new_text)} characters")
    print(f"  Image rotation: set to 0 (no rotation needed)")

    conn.close()
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
