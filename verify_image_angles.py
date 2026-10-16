#!/usr/bin/env python3
"""
Verify image angles using Claude's vision API to determine correct rotation.
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

def check_image_orientation(article_id, image_path):
    """Check image orientation and suggest correct rotation."""
    if not image_path.exists():
        print(f"  ERROR: Image not found: {image_path}")
        return None

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    message = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=1024,
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
                        "text": "Analyze this image's orientation. Is it:\n1. Correct/straight (right-side up)\n2. Upside down (180 degrees)\n3. Rotated 90 degrees clockwise\n4. Rotated 90 degrees counterclockwise\n\nRespond with ONLY one number (1, 2, 3, or 4) and brief reasoning."
                    }
                ],
            }
        ],
    )

    response = message.content[0].text if hasattr(message.content[0], 'text') else ""
    return response.strip()

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Articles to check
    articles = [1508, 1510, 1515, 1517]

    print("Verifying image orientations using Claude's vision API...\n")

    for article_id in articles:
        cursor.execute(
            "SELECT file_name, folder_name, image_rotation FROM articles WHERE id = ?",
            (article_id,)
        )
        result = cursor.fetchone()

        if not result:
            print(f"Article {article_id}: NOT FOUND")
            continue

        file_name, folder_name, current_rotation = result
        image_path = PROJECT_DIR / "images" / folder_name / file_name

        print(f"Article {article_id}: {file_name}")
        print(f"  Current rotation: {current_rotation} degrees")

        orientation = check_image_orientation(article_id, image_path)
        print(f"  Vision AI analysis: {orientation}")
        print()

    conn.close()

if __name__ == "__main__":
    main()
