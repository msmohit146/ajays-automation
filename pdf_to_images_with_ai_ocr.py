#!/usr/bin/env python3
"""
Convert PDFs to images and extract OCR with Claude AI vision.
"""

import sqlite3
import json
from pathlib import Path
import subprocess
import base64
from datetime import datetime

db_path = Path("archive.db")
IMAGE_DIR = Path("images")

def convert_pdf_to_images(pdf_path: Path) -> list[Path]:
    """Convert PDF to JPEG images using pdftoppm."""
    try:
        output_prefix = pdf_path.parent / pdf_path.stem

        # Convert PDF to JPEG with 150 DPI
        result = subprocess.run(
            ["pdftoppm", str(pdf_path), str(output_prefix), "-jpeg", "-r", "150"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return []

        # Find generated images
        generated_images = sorted(output_prefix.parent.glob(f"{pdf_path.stem}-*.jpg"))
        return generated_images

    except Exception as e:
        print(f"Error converting {pdf_path.name}: {e}")
        return []

def extract_text_with_claude(image_path: Path, page_num: int = 1) -> str:
    """Extract text from image using Claude vision API."""
    try:
        import anthropic

        # Read image
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        # Call Claude
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-opus-5-5",
            max_tokens=4000,
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
                            "text": f"""Extract ALL text from this document page with 100% accuracy.

Page: {page_num}

Instructions:
1. Read every word, number, and symbol visible
2. Preserve original layout and structure
3. If multi-column, read left-to-right, top-to-bottom
4. Include headers, footers, page numbers
5. Do NOT skip any content
6. Maintain formatting (line breaks, indentation, etc.)

Return ONLY the extracted text, nothing else."""
                        }
                    ],
                }
            ],
        )

        return message.content[0].text

    except Exception as e:
        print(f"Error extracting text from {image_path.name}: {e}")
        return None

def main():
    print("PDF to Images with AI OCR Correction")
    print("=" * 70)

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

    print(f"Found {len(pdf_articles)} PDF articles to process\n")

    conversion_report = {
        "timestamp": datetime.now().isoformat(),
        "total_pdfs": len(pdf_articles),
        "successfully_processed": 0,
        "failed": 0,
        "conversions": []
    }

    for idx, (article_id, file_name, file_path) in enumerate(pdf_articles, 1):
        # Resolve PDF path
        if file_path.startswith("images/"):
            pdf_full_path = IMAGE_DIR / file_path[7:]
        else:
            pdf_full_path = IMAGE_DIR / file_path

        if not pdf_full_path.exists():
            print(f"[{idx:3d}/{len(pdf_articles)}] ✗ ID {article_id}: FILE NOT FOUND")
            conversion_report["failed"] += 1
            continue

        print(f"[{idx:3d}/{len(pdf_articles)}] Processing ID {article_id}: {file_name}...", flush=True)

        # Step 1: Convert PDF to images
        print(f"  → Converting PDF to images...", end=" ", flush=True)
        image_paths = convert_pdf_to_images(pdf_full_path)

        if not image_paths:
            print("✗ CONVERSION FAILED")
            conversion_report["failed"] += 1
            conversion_report["conversions"].append({
                "id": article_id,
                "file_name": file_name,
                "status": "failed",
                "reason": "PDF conversion failed"
            })
            continue

        print(f"✓ ({len(image_paths)} page{'s' if len(image_paths) > 1 else ''})")

        # Step 2: Extract text from images with Claude
        print(f"  → Extracting text with Claude AI...", end=" ", flush=True)
        all_text = []
        for page_num, image_path in enumerate(image_paths, 1):
            extracted = extract_text_with_claude(image_path, page_num)
            if extracted:
                all_text.append(f"[OCR page {page_num}]\n{extracted}")

        if not all_text:
            print("✗ TEXT EXTRACTION FAILED")
            conversion_report["failed"] += 1
            conversion_report["conversions"].append({
                "id": article_id,
                "file_name": file_name,
                "status": "failed",
                "reason": "Text extraction failed"
            })
            continue

        combined_text = "\n\n".join(all_text)
        print(f"✓ ({len(combined_text)} chars)")

        # Step 3: Update database
        # Use the first image as the primary image
        first_image_relative = str(image_paths[0].relative_to(IMAGE_DIR))

        cursor.execute("""
            UPDATE articles
            SET file_path = ?, parsed_text = ?, file_name = ?
            WHERE id = ?
        """, (f"images/{first_image_relative}", combined_text, image_paths[0].name, article_id))
        conn.commit()

        conversion_report["successfully_processed"] += 1
        conversion_report["conversions"].append({
            "id": article_id,
            "file_name": file_name,
            "original_pdf": file_path,
            "new_image_path": f"images/{first_image_relative}",
            "page_count": len(image_paths),
            "text_length": len(combined_text),
            "status": "completed"
        })

        print(f"  → Updated database ✓\n")

    conn.close()

    # Save report
    with open("pdf_conversion_complete_report.json", "w") as f:
        json.dump(conversion_report, f, indent=2)

    print("\n" + "=" * 70)
    print(f"Completed: {conversion_report['successfully_processed']}/{len(pdf_articles)}")
    print(f"Failed: {conversion_report['failed']}")
    print(f"Report: pdf_conversion_complete_report.json")

if __name__ == "__main__":
    main()
