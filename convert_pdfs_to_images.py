#!/usr/bin/env python3
"""
Convert PDF files to images and extract OCR using Claude vision.
"""

import sqlite3
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image
import io

db_path = Path("archive.db")
IMAGE_DIR = Path("images")

def convert_pdf_to_images(pdf_path: Path) -> list[Path]:
    """Convert PDF to images using pdftoppm (from Poppler)."""
    try:
        # Output images will be named with -001, -002, etc. for multiple pages
        output_prefix = pdf_path.parent / pdf_path.stem

        # Use pdftoppm to convert PDF to PPM (then we can convert to JPEG)
        result = subprocess.run(
            ["pdftoppm", str(pdf_path), str(output_prefix), "-jpeg", "-r", "150"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            print(f"  pdftoppm error: {result.stderr}")
            return []

        # Find the generated images
        generated_images = sorted(output_prefix.parent.glob(f"{pdf_path.stem}-*.jpg"))
        return generated_images

    except FileNotFoundError:
        print("  pdftoppm not found. Install Poppler: choco install poppler")
        return []
    except Exception as e:
        print(f"  Error converting PDF: {e}")
        return []

def extract_text_with_claude(image_path: Path) -> str:
    """Use Claude to extract text from image via the Read tool."""
    try:
        # For this to work in our environment, we need to use Claude directly
        # Since we're in a Python script outside the agent, we need to use the API
        # For now, we'll create a placeholder that the user will need to fill in

        print(f"    [Would extract text from {image_path.name} using Claude vision]")
        return None  # Placeholder

    except Exception as e:
        print(f"    Error extracting text: {e}")
        return None

def main():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all PDF articles
    cursor.execute("""
        SELECT id, file_name, file_path
        FROM articles
        WHERE file_path LIKE '%.pdf%' OR file_name LIKE '%.pdf%'
        ORDER BY id
    """)
    pdf_articles = cursor.fetchall()

    print(f"Found {len(pdf_articles)} PDF articles to convert")
    print("=" * 60)

    conversion_report = {
        "total_pdfs": len(pdf_articles),
        "successfully_converted": 0,
        "conversion_errors": 0,
        "conversions": []
    }

    for idx, (article_id, file_name, file_path) in enumerate(pdf_articles, 1):
        # Resolve PDF path
        if file_path.startswith("images/"):
            pdf_full_path = IMAGE_DIR / file_path[7:]
        else:
            pdf_full_path = IMAGE_DIR / file_path

        if not pdf_full_path.exists():
            print(f"[{idx}/{len(pdf_articles)}] ✗ ID {article_id}: PDF NOT FOUND")
            conversion_report["conversion_errors"] += 1
            continue

        print(f"[{idx}/{len(pdf_articles)}] Converting ID {article_id}: {file_name}...", end=" ", flush=True)

        # Convert PDF to images
        image_paths = convert_pdf_to_images(pdf_full_path)

        if image_paths:
            print(f"✓ ({len(image_paths)} page(s))")
            conversion_report["successfully_converted"] += 1

            conversion_report["conversions"].append({
                "id": article_id,
                "file_name": file_name,
                "original_pdf": file_path,
                "generated_images": [str(img.relative_to(IMAGE_DIR)) for img in image_paths],
                "page_count": len(image_paths),
                "status": "converted"
            })
        else:
            print(f"✗ FAILED")
            conversion_report["conversion_errors"] += 1
            conversion_report["conversions"].append({
                "id": article_id,
                "file_name": file_name,
                "status": "failed"
            })

    conn.close()

    # Save report
    with open("pdf_conversion_report.json", "w") as f:
        json.dump(conversion_report, f, indent=2)

    print("\n" + "=" * 60)
    print(f"Converted: {conversion_report['successfully_converted']}/{len(pdf_articles)}")
    print(f"Failed: {conversion_report['conversion_errors']}")
    print(f"Report saved to: pdf_conversion_report.json")
    print("\nNext steps:")
    print("1. Check pdf_conversion_report.json for conversion results")
    print("2. Run Claude vision extraction on the generated images")
    print("3. Update database with new image paths and OCR text")

if __name__ == "__main__":
    main()
