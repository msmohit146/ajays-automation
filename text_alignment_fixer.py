import anthropic
import sqlite3
import base64
import os
from pathlib import Path
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not set. Create .env file with your API key.")

db_path = "archive.db"
client = anthropic.Anthropic(api_key=api_key)

def fix_text_with_image(file_name, file_path, extracted_text):
    """Use Claude vision to fix text ordering based on image layout"""

    if not os.path.exists(file_path):
        return extracted_text

    # Read image and encode to base64
    with open(file_path, "rb") as img_file:
        image_data = base64.standard_b64encode(img_file.read()).decode("utf-8")

    # Determine media type
    ext = Path(file_path).suffix.lower()
    media_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"

    # Call Claude to analyze and fix text
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": f"""This is a newspaper article image. Here is the OCR-extracted text:

{extracted_text}

The text appears to be jumbled across multiple columns. Please:
1. Analyze the image layout to identify column positions
2. Reorganize the extracted text to read properly column-by-column (left to right, top to bottom)
3. Fix any obvious OCR errors where you can see the correct text in the image
4. Return ONLY the corrected text, no explanations

If you cannot identify clear columns, return the text as-is. Focus on readability and proper reading order."""
                    }
                ],
            }
        ],
    )

    return message.content[0].text

def process_articles(limit=None):
    """Process articles and fix text alignment"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id, file_name, file_path, parsed_text FROM articles ORDER BY id")
    articles = cursor.fetchall()

    if limit:
        articles = articles[:limit]

    updated = 0
    for idx, (article_id, file_name, file_path, parsed_text) in enumerate(articles, 1):
        print(f"[{idx}/{len(articles)}] Processing {file_name}...", end=" ", flush=True)

        if not parsed_text or len(parsed_text.strip()) < 50:
            print("SKIP (empty/too short)")
            continue

        try:
            fixed_text = fix_text_with_image(file_name, file_path, parsed_text)

            if fixed_text != parsed_text:
                cursor.execute("UPDATE articles SET parsed_text = ? WHERE id = ?",
                             (fixed_text, article_id))
                conn.commit()
                updated += 1
                print("FIXED")
            else:
                print("OK")
        except Exception as e:
            print(f"ERROR: {e}")

    conn.close()
    print(f"\nUpdated {updated} articles")

if __name__ == "__main__":
    print("Starting text alignment fix with vision AI...")
    # Process all articles
    process_articles()
