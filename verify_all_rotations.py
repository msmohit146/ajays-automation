#!/usr/bin/env python3
"""
Verify all image rotations using Claude's vision API.
"""

import sqlite3
import base64
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

DB_PATH = Path("archive.db")
PROJECT_DIR = Path(__file__).parent

client = Anthropic()

def check_image_rotation(article_id, image_path):
    """Check if image is in correct angle."""
    if not image_path.exists():
        return f"ERROR: Image not found"

    try:
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        message = client.messages.create(
            model="claude-sonnet-5-5",
            max_tokens=256,
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
                            "text": "Is this image straight/correct (1) or upside down/rotated (2-4)? Answer with: CORRECT if straight, or UPSIDE-DOWN if flipped 180, or ROTATED-90 if rotated 90 degrees."
                        }
                    ],
                }
            ],
        )

        response = ""
        for block in message.content:
            if hasattr(block, 'text'):
                response = block.text.strip().upper()

        return response
    except Exception as e:
        return f"ERROR: {str(e)}"

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Articles to check
    articles = [1508, 1510, 1515, 1517, 2041, 1557]

    print("\n" + "=" * 100)
    print("IMAGE ROTATION VERIFICATION REPORT")
    print("=" * 100 + "\n")

    results = []

    for article_id in articles:
        cursor.execute(
            "SELECT file_name, folder_name, image_rotation FROM articles WHERE id = ?",
            (article_id,)
        )
        result = cursor.fetchone()

        if not result:
            print(f"Article {article_id}: NOT FOUND\n")
            continue

        file_name, folder_name, current_rotation = result
        image_path = PROJECT_DIR / "images" / folder_name / file_name

        print(f"Article {article_id}")
        print(f"  File: {file_name}")
        print(f"  Folder: {folder_name}")
        print(f"  Database rotation: {current_rotation}°")
        print(f"  Checking image...", end=" ", flush=True)

        status = check_image_rotation(article_id, image_path)
        print(f"Status: {status}")

        if "CORRECT" in status:
            result_icon = "✓ FIXED"
        elif "ERROR" in status:
            result_icon = "? ERROR"
        else:
            result_icon = "✗ NEEDS FIX"

        results.append((article_id, current_rotation, status, result_icon))
        print()

    # Summary
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    for article_id, rotation, status, icon in results:
        print(f"{icon}  Article {article_id}: rotation={rotation}° → {status}")

    conn.close()

if __name__ == "__main__":
    main()
