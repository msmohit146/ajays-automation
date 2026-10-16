#!/usr/bin/env python3
"""
Correct OCR text for 73 problem articles (55 PDFs + 18 garbled images)
using Claude's vision capabilities.
"""

import sqlite3
import json
import sys
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
REPORT_FILE = Path("ocr_correction_report.json")
BATCH_SIZE = 5  # Process 5 items at a time

# Problem article IDs
GARBLED_IDS = [150, 151, 152, 153, 154, 155, 156, 676, 1541, 1542, 1543, 1544, 1545, 1546, 1548, 1549, 2022, 2051]

# Track corrections
corrections = []
errors = []

def get_articles_to_fix():
    """Get all articles that need OCR correction"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    articles = []

    # Get PDF articles
    cursor.execute("""
        SELECT id, file_name, file_path
        FROM articles
        WHERE file_path LIKE '%.pdf%' OR file_name LIKE '%.pdf%'
        ORDER BY id
    """)
    pdf_articles = cursor.fetchall()

    # Get garbled articles
    cursor.execute("""
        SELECT id, file_name, file_path
        FROM articles
        WHERE id IN ({})
        ORDER BY id
    """.format(",".join("?" * len(GARBLED_IDS))), GARBLED_IDS)
    garbled_articles = cursor.fetchall()

    conn.close()

    return pdf_articles + garbled_articles

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
    if ext in ['.jpg', '.jpeg']:
        return "image/jpeg"
    elif ext == '.png':
        return "image/png"
    elif ext == '.gif':
        return "image/gif"
    elif ext == '.webp':
        return "image/webp"
    else:
        return "image/jpeg"  # Default

async def extract_text_from_image(client, image_path, article_id, file_name):
    """Extract text from image using Claude's vision"""
    try:
        # Read and encode image
        image_base64 = get_image_base64(image_path)
        media_type = get_image_media_type(image_path)

        # Call Claude vision API
        message = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
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
3. Fix any obvious OCR errors, but preserve the original content
4. Include all visible text, even if it seems garbled or unusual
5. Return ONLY the extracted text, no commentary

If this is a document with multiple columns, organize them in reading order (left to right, top to bottom).
If this is a newspaper article with headers/titles, preserve those.

Extracted text:"""
                        }
                    ]
                }
            ]
        )

        extracted_text = message.content[0].text.strip()
        return extracted_text

    except Exception as e:
        error_msg = f"Failed to extract text from image {article_id} ({file_name}): {str(e)}"
        print(f"✗ {error_msg}")
        errors.append({"id": article_id, "file": file_name, "error": str(e)})
        return None

async def extract_text_from_pdf(client, pdf_path, article_id, file_name):
    """Extract text from PDF by converting to images"""
    try:
        # Try to import pdf2image
        try:
            from pdf2image import convert_from_path
        except ImportError:
            print(f"⚠ pdf2image not available, trying alternative method for {file_name}")
            return None

        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=150, first_page=1, last_page=None)

        if not images:
            return None

        extracted_texts = []

        # Process first few pages (limit to avoid too many API calls)
        for page_num, image in enumerate(images[:10], 1):
            try:
                # Convert PIL image to bytes
                import io
                image_bytes = io.BytesIO()
                image.save(image_bytes, format='PNG')
                image_base64 = base64.standard_b64encode(image_bytes.getvalue()).decode("utf-8")

                # Call Claude vision API for this page
                message = await client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2048,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": image_base64
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": f"""Extract all text from this PDF page ({page_num}) with 100% accuracy.

Instructions:
1. Read every word carefully
2. Preserve formatting and structure
3. Include all visible text
4. Return ONLY the text, no commentary

Extracted text:"""
                                }
                            ]
                        }
                    ]
                )

                page_text = message.content[0].text.strip()
                if page_text:
                    extracted_texts.append(f"--- Page {page_num} ---\n{page_text}")

            except Exception as e:
                print(f"  Warning: Failed to process page {page_num}: {e}")
                continue

        return "\n\n".join(extracted_texts) if extracted_texts else None

    except Exception as e:
        error_msg = f"Failed to extract text from PDF {article_id} ({file_name}): {str(e)}"
        print(f"✗ {error_msg}")
        errors.append({"id": article_id, "file": file_name, "error": str(e)})
        return None

async def process_article(client, article_id, file_name, file_path):
    """Process a single article"""
    try:
        # Resolve file path
        full_path = resolve_file_path(file_path)
        if not full_path:
            error_msg = f"File not found: {file_path}"
            print(f"✗ ID {article_id}: {error_msg}")
            errors.append({"id": article_id, "file": file_name, "error": error_msg})
            return None

        # Extract text based on file type
        if full_path.lower().endswith('.pdf'):
            print(f"⏳ ID {article_id}: Extracting from PDF {file_name}...")
            extracted_text = await extract_text_from_pdf(client, full_path, article_id, file_name)
        else:
            print(f"⏳ ID {article_id}: Extracting from image {file_name}...")
            extracted_text = await extract_text_from_image(client, full_path, article_id, file_name)

        if extracted_text:
            print(f"✓ ID {article_id}: Successfully extracted {len(extracted_text)} chars")
            return extracted_text
        else:
            error_msg = "Could not extract text"
            print(f"✗ ID {article_id}: {error_msg}")
            errors.append({"id": article_id, "file": file_name, "error": error_msg})
            return None

    except Exception as e:
        print(f"✗ ID {article_id}: Exception - {str(e)}")
        errors.append({"id": article_id, "file": file_name, "error": str(e)})
        traceback.print_exc()
        return None

async def update_database(article_id, extracted_text):
    """Update database with corrected text"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get original text for comparison
        cursor.execute("SELECT parsed_text FROM articles WHERE id = ?", (article_id,))
        result = cursor.fetchone()
        original_text = result[0] if result else ""

        # Update with new text
        cursor.execute(
            "UPDATE articles SET parsed_text = ? WHERE id = ?",
            (extracted_text, article_id)
        )
        conn.commit()
        conn.close()

        # Track correction
        corrections.append({
            "id": article_id,
            "original_length": len(original_text) if original_text else 0,
            "corrected_length": len(extracted_text),
            "timestamp": datetime.now().isoformat()
        })

        return True
    except Exception as e:
        print(f"✗ Database update failed for ID {article_id}: {e}")
        errors.append({"id": article_id, "error": f"Database update: {e}"})
        return False

async def process_batch(client, articles):
    """Process a batch of articles"""
    tasks = []
    for article_id, file_name, file_path in articles:
        tasks.append(process_article(client, article_id, file_name, file_path))

    results = await asyncio.gather(*tasks)

    # Update database for successful extractions
    for (article_id, _, _), extracted_text in zip(articles, results):
        if extracted_text:
            await update_database(article_id, extracted_text)

async def main():
    """Main function"""
    print("=" * 70)
    print("OCR CORRECTION WITH CLAUDE VISION")
    print("=" * 70)

    # Get articles to fix
    articles = get_articles_to_fix()
    print(f"\nFound {len(articles)} articles to fix")
    print(f"  - PDFs: 55")
    print(f"  - Garbled images: 18")

    if not articles:
        print("No articles to process!")
        return

    # Initialize Claude client
    client = AsyncAnthropic()

    print("\nStarting extraction process...")
    print("-" * 70)

    # Process in batches
    total = len(articles)
    for i in range(0, total, BATCH_SIZE):
        batch = articles[i:i+BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\n[Batch {batch_num}/{total_batches}]")
        await process_batch(client, batch)

        # Small delay between batches
        if i + BATCH_SIZE < total:
            await asyncio.sleep(1)

    print("\n" + "=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)

    # Print summary
    print(f"\nSummary:")
    print(f"  Processed: {len(articles)} articles")
    print(f"  Corrected: {len(corrections)}")
    print(f"  Errors: {len(errors)}")

    if errors:
        print(f"\nErrors encountered:")
        for error in errors[:10]:
            print(f"  - ID {error.get('id', 'N/A')}: {error.get('error', 'Unknown')}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_processed": len(articles),
        "total_corrected": len(corrections),
        "total_errors": len(errors),
        "corrections": corrections,
        "errors": errors
    }

    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved to {REPORT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
