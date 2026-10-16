#!/usr/bin/env python3
"""
Convert PDFs to images with PyMuPDF and extract OCR with Claude AI.
"""

import sqlite3
import json
from pathlib import Path
import fitz  # PyMuPDF
from datetime import datetime
import base64

db_path = Path("archive.db")
IMAGE_DIR = Path("images")

def convert_pdf_to_images(pdf_path: Path) -> list[Path]:
    """Convert PDF pages to JPEG images using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        image_paths = []

        for page_num, page in enumerate(doc, 1):
            # Render page to image (300 DPI)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

            # Save as JPEG
            image_name = f"{pdf_path.stem}-{page_num:03d}.jpg"
            image_path = pdf_path.parent / image_name
            pix.save(image_path)
            image_paths.append(image_path)

        doc.close()
        return image_paths

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

Page {page_num}

Instructions:
1. Read every word, number, and symbol visible
2. Preserve original layout and structure
3. If multi-column, read left-to-right, top-to-bottom
4. Include headers, footers, page numbers
5. Do NOT skip any content
6. Maintain formatting (line breaks, indentation)

Return ONLY the extracted text."""
                        }
                    ],
                }
            ],
        )

        return message.content[0].text

    except Exception as e:
        print(f"Error extracting text: {e}")
        return None

def main():
    print("Converting PDFs to Images with AI OCR")
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

    print(f"Found {len(pdf_articles)} PDF articles\n")

    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(pdf_articles),
        "success": 0,
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
            report["failed"] += 1
            continue

        print(f"[{idx:3d}/{len(pdf_articles)}] ID {article_id}: {file_name}...", flush=True)

        # Convert PDF to images
        print(f"  • Converting PDF...", end=" ", flush=True)
        image_paths = convert_pdf_to_images(pdf_full_path)

        if not image_paths:
            print("✗ FAILED")
            report["failed"] += 1
            report["conversions"].append({
                "id": article_id,
                "status": "failed",
                "reason": "Conversion failed"
            })
            continue

        print(f"✓ ({len(image_paths)} pages)")

        # Extract text with Claude
        print(f"  • Extracting text with AI...", end=" ", flush=True)
        all_text = []
        for page_num, image_path in enumerate(image_paths, 1):
            text = extract_text_with_claude(image_path, page_num)
            if text:
                all_text.append(f"[OCR page {page_num}]\n{text}")

        if not all_text:
            print("✗ FAILED")
            report["failed"] += 1
            continue

        combined_text = "\n\n".join(all_text)
        print(f"✓ ({len(combined_text)} chars)")

        # Update database with first image path
        new_file_path = f"images/{image_paths[0].relative_to(IMAGE_DIR)}"
        new_file_name = image_paths[0].name

        cursor.execute("""
            UPDATE articles
            SET file_path = ?, file_name = ?, parsed_text = ?
            WHERE id = ?
        """, (new_file_path, new_file_name, combined_text, article_id))
        conn.commit()

        print(f"  • Updated database ✓\n")
        report["success"] += 1
        report["conversions"].append({
            "id": article_id,
            "file_name": file_name,
            "status": "converted",
            "pages": len(image_paths),
            "text_chars": len(combined_text),
            "new_image": new_file_path
        })

    conn.close()

    # Save report
    with open("pdf_conversion_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 70)
    print(f"✓ Success: {report['success']}/{len(pdf_articles)}")
    print(f"✗ Failed: {report['failed']}")
    print(f"Report: pdf_conversion_report.json")

if __name__ == "__main__":
    main()
