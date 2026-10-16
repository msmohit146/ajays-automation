#!/usr/bin/env python3
"""
Test OCR correction on a small batch (first 5 files)
"""

import sqlite3
import json
import sys
import base64
import asyncio
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

# Load environment variables
load_dotenv()

DB_PATH = Path("archive.db")
IMAGES_DIR = Path("images")
GARBLED_IDS = [150, 151, 152, 153, 154, 155, 156, 676, 1541, 1542, 1543, 1544, 1545, 1546, 1548, 1549, 2022, 2051]

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
    """Resolve file path"""
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
    """Read image and convert to base64"""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def get_image_media_type(file_path):
    """Get media type"""
    ext = Path(file_path).suffix.lower()
    if ext in ['.jpg', '.jpeg']:
        return "image/jpeg"
    elif ext == '.png':
        return "image/png"
    else:
        return "image/jpeg"

async def extract_from_image(client, image_path):
    """Extract text from image"""
    image_base64 = get_image_base64(image_path)
    media_type = get_image_media_type(image_path)

    message = await client.messages.create(
        model="claude-3-sonnet-20250219",
        max_tokens=2048,
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
                        "text": "Extract ALL text from this image with 100% accuracy. Return only the extracted text, no commentary."
                    }
                ]
            }
        ]
    )

    return message.content[0].text.strip()

async def extract_from_pdf(client, pdf_path):
    """Extract text from PDF using pdfplumber to render pages as images"""
    try:
        import pdfplumber
        import io
        from PIL import Image

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            pages_to_process = min(3, total_pages)

            texts = []
            for page_num in range(pages_to_process):
                try:
                    page = pdf.pages[page_num]

                    # Render page to image
                    pil_image = page.to_image(resolution=150).original

                    # Convert to base64
                    image_bytes = io.BytesIO()
                    pil_image.save(image_bytes, format='PNG')
                    image_base64 = base64.standard_b64encode(image_bytes.getvalue()).decode("utf-8")

                    # Send to Claude
                    message = await client.messages.create(
                        model="claude-3-sonnet-20250219",
                        max_tokens=1024,
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
                                        "text": f"Extract all text from page {page_num + 1}. Return only the text, no commentary."
                                    }
                                ]
                            }
                        ]
                    )

                    text = message.content[0].text.strip()
                    if text:
                        texts.append(f"--- Page {page_num + 1} ---\n{text}")
                except Exception as e:
                    print(f"    Warning: Failed to process page {page_num + 1}: {e}")

            return "\n\n".join(texts) if texts else None
    except Exception as e:
        print(f"    Error: {e}")
        return None

async def test_extraction(client, articles):
    """Test on first 5 articles"""
    for article_id, file_name, file_path in articles[:5]:
        try:
            full_path = resolve_file_path(file_path)
            if not full_path:
                print(f"✗ ID {article_id}: File not found - {file_path}")
                continue

            print(f"\nProcessing ID {article_id}: {file_name}")
            print(f"  Path: {full_path}")
            print(f"  Size: {Path(full_path).stat().st_size / (1024*1024):.1f} MB")

            if full_path.lower().endswith('.pdf'):
                print("  Type: PDF")
                text = await extract_from_pdf(client, full_path)
            else:
                print("  Type: Image")
                text = await extract_from_image(client, full_path)

            if text:
                print(f"  Extracted: {len(text)} characters")
                print(f"  Preview: {text[:200]}...")
            else:
                print("  ✗ No text extracted")

        except Exception as e:
            print(f"✗ ID {article_id}: {e}")
            import traceback
            traceback.print_exc()

async def main():
    print("=" * 70)
    print("OCR TEST - First 5 Files")
    print("=" * 70)

    articles = get_articles_to_fix()
    print(f"\nTotal articles to process: {len(articles)}")
    print(f"Testing first 5...\n")

    client = AsyncAnthropic()
    await test_extraction(client, articles)

if __name__ == "__main__":
    asyncio.run(main())
