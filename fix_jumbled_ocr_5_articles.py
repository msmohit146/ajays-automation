#!/usr/bin/env python3
"""
Fix 5 articles with jumbled OCR text by extracting the correct text from
their JPEG images using Claude's vision capabilities.

Article IDs: 1724, 1763, 1774, 1853, 1875
"""

import sqlite3
import json
import base64
import asyncio
from pathlib import Path
from datetime import datetime
import traceback
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

# Load environment variables from .env file
load_dotenv()

# Configuration
DB_PATH = Path("archive.db")
IMAGES_DIR = Path("images")
REPORT_FILE = Path("jumbled_ocr_fix_report.json")

# Article IDs to fix
ARTICLE_IDS = [1724, 1763, 1774, 1853, 1875]

# Track results
corrections = []
errors = []


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
    try:
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")
    except Exception as e:
        raise Exception(f"Failed to read image {image_path}: {e}")


def get_image_media_type(file_path):
    """Get media type based on file extension"""
    ext = Path(file_path).suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif ext == ".png":
        return "image/png"
    elif ext == ".gif":
        return "image/gif"
    elif ext == ".webp":
        return "image/webp"
    else:
        return "image/jpeg"  # Default


def get_article_data(article_id):
    """Get article data from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, file_name, file_path, parsed_text FROM articles WHERE id = ?",
            (article_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception as e:
        print(f"[ERROR] Database read failed for ID {article_id}: {e}")
        errors.append({"id": article_id, "error": f"Database read: {e}"})
        return None


async def extract_text_from_image(client, image_path, article_id, file_name):
    """Extract text from image using Claude's vision"""
    try:
        # Read and encode image
        image_base64 = get_image_base64(image_path)
        media_type = get_image_media_type(image_path)

        # Call Claude vision API
        message = await client.messages.create(
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
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": """Please extract ALL text from this image with 100% accuracy.

Instructions:
1. Read every word carefully, including headers, footers, and any text in multiple columns
2. Preserve the structure (paragraphs, line breaks, etc.)
3. Fix any obvious OCR errors, but preserve the original content
4. Include all visible text, even if it seems garbled or unusual
5. Return ONLY the extracted text, no commentary

If this is a document with multiple columns, organize them in reading order (left to right, top to bottom).
If this is a newspaper article with headers/titles, preserve those.

Extracted text:""",
                        },
                    ],
                }
            ],
        )

        # Extract text from content blocks (skip thinking blocks)
        for block in message.content:
            if block.type == "text":
                return block.text.strip()

        # If no text block found, return None
        return None

    except Exception as e:
        error_msg = (
            f"Failed to extract text from image {article_id} ({file_name}): {str(e)}"
        )
        print(f"[ERROR] {error_msg}")
        errors.append(
            {"id": article_id, "file": file_name, "error": str(e)}
        )
        return None


async def process_article(client, article_id):
    """Process a single article"""
    try:
        # Get article data
        article_data = get_article_data(article_id)
        if not article_data:
            print(f"[ERROR] ID {article_id}: Article not found in database")
            return None

        _, file_name, file_path, original_text = article_data

        # Resolve file path
        full_path = resolve_file_path(file_path)
        if not full_path:
            error_msg = f"File not found: {file_path}"
            print(f"[ERROR] ID {article_id}: {error_msg}")
            errors.append({"id": article_id, "file": file_name, "error": error_msg})
            return None

        # Check file exists
        if not Path(full_path).exists():
            error_msg = f"File does not exist: {full_path}"
            print(f"[ERROR] ID {article_id}: {error_msg}")
            errors.append({"id": article_id, "file": file_name, "error": error_msg})
            return None

        # Extract text from image
        print(f"[...] ID {article_id}: Extracting text from {file_name}...")
        extracted_text = await extract_text_from_image(
            client, full_path, article_id, file_name
        )

        if extracted_text:
            print(
                f"[OK] ID {article_id}: Successfully extracted {len(extracted_text)} chars"
            )
            return {
                "id": article_id,
                "file_name": file_name,
                "file_path": file_path,
                "original_length": len(original_text) if original_text else 0,
                "extracted_text": extracted_text,
                "new_length": len(extracted_text),
            }
        else:
            error_msg = "Could not extract text"
            print(f"[ERROR] ID {article_id}: {error_msg}")
            errors.append(
                {"id": article_id, "file": file_name, "error": error_msg}
            )
            return None

    except Exception as e:
        print(f"[ERROR] ID {article_id}: Exception - {str(e)}")
        errors.append({"id": article_id, "error": str(e)})
        traceback.print_exc()
        return None


async def update_database(article_id, extracted_text):
    """Update database with corrected text"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Update with new text
        cursor.execute(
            "UPDATE articles SET parsed_text = ? WHERE id = ?",
            (extracted_text, article_id),
        )
        conn.commit()
        conn.close()

        return True
    except Exception as e:
        print(f"[ERROR] Database update failed for ID {article_id}: {e}")
        errors.append({"id": article_id, "error": f"Database update: {e}"})
        return False


async def main():
    """Main function"""
    print("=" * 70)
    print("FIX JUMBLED OCR TEXT FOR 5 ARTICLES USING CLAUDE VISION")
    print("=" * 70)
    print()

    # Check database exists
    if not DB_PATH.exists():
        print(f"✗ Database not found: {DB_PATH}")
        return

    print(f"Database: {DB_PATH.absolute()}")
    print(f"Articles to fix: {ARTICLE_IDS}")
    print()

    # Initialize Claude client
    client = AsyncAnthropic()

    print("Starting extraction and correction process...")
    print("-" * 70)

    # Process each article
    results = []
    for article_id in ARTICLE_IDS:
        result = await process_article(client, article_id)
        if result:
            results.append(result)
        print()

    # Update database for successful extractions
    print("-" * 70)
    print("Updating database with corrected text...")
    print()

    updated_count = 0
    for result in results:
        article_id = result["id"]
        extracted_text = result["extracted_text"]

        if await update_database(article_id, extracted_text):
            print(f"[OK] ID {article_id}: Database updated successfully")
            corrections.append(
                {
                    "id": article_id,
                    "file": result["file_name"],
                    "original_length": result["original_length"],
                    "new_length": result["new_length"],
                    "timestamp": datetime.now().isoformat(),
                }
            )
            updated_count += 1
        else:
            print(f"[ERROR] ID {article_id}: Failed to update database")

    print()
    print("=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)

    # Print summary
    print()
    print("Summary:")
    print(f"  Total articles: {len(ARTICLE_IDS)}")
    print(f"  Successfully extracted: {len(results)}")
    print(f"  Database updated: {updated_count}")
    print(f"  Errors: {len(errors)}")

    if errors:
        print()
        print("Errors encountered:")
        for error in errors:
            error_id = error.get("id", "N/A")
            error_msg = error.get("error", "Unknown")
            print(f"  * ID {error_id}: {error_msg}")

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_articles": len(ARTICLE_IDS),
        "total_extracted": len(results),
        "total_updated": updated_count,
        "total_errors": len(errors),
        "corrections": corrections,
        "errors": errors,
    }

    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    print()
    print(f"Report saved to {REPORT_FILE.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())
