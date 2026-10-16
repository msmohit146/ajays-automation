#!/usr/bin/env python3
"""
Correct OCR text for PDF and garbled articles using Claude's vision API.
Processes all files with high accuracy using Claude AI.
"""

import sqlite3
import json
from pathlib import Path
import base64
import anthropic

db_path = Path("archive.db")
IMAGE_DIR = Path("images")

def read_file_as_base64(file_path: Path) -> str:
    """Read file and encode as base64."""
    with open(file_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def get_media_type(file_path: Path) -> str:
    """Get media type for file."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    elif suffix in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif suffix == ".png":
        return "image/png"
    else:
        return "image/jpeg"  # default

def extract_text_with_claude(file_path: Path) -> str:
    """Use Claude's vision to extract text from image/PDF."""
    try:
        # Initialize Anthropic client
        client = anthropic.Anthropic()

        # Read file as base64
        file_data = read_file_as_base64(file_path)
        media_type = get_media_type(file_path)

        # Call Claude with vision
        message = client.messages.create(
            model="claude-opus-5-5",  # Use most capable model for accuracy
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": file_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": """Extract ALL text from this document with 100% accuracy.

Instructions:
1. Read every word, number, and symbol visible
2. Preserve the original layout and structure
3. If it's a PDF with multiple pages, extract all pages in order
4. If text is in multiple columns, read left-to-right, top-to-bottom
5. Include ALL text including headers, footers, page numbers
6. Do NOT skip any content
7. Maintain original formatting (line breaks, indentation, etc.)

Return ONLY the extracted text, nothing else."""
                        }
                    ],
                }
            ],
        )

        return message.content[0].text
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def main():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get PDF and garbled articles
    cursor.execute("""
        SELECT id, file_name, file_path
        FROM articles
        WHERE file_path LIKE '%.pdf%' OR file_name LIKE '%.pdf%'
        ORDER BY id
    """)
    pdf_articles = cursor.fetchall()

    garbled_ids = [150, 151, 152, 153, 154, 155, 156, 676, 1541, 1542, 1543, 1544, 1545, 1546, 1548, 1549, 2022, 2051]
    cursor.execute("SELECT id, file_name, file_path FROM articles WHERE id IN ({})".format(
        ",".join("?" * len(garbled_ids))
    ), garbled_ids)
    garbled_articles = cursor.fetchall()

    all_articles = pdf_articles + garbled_articles
    total = len(all_articles)

    print(f"Processing {total} articles ({len(pdf_articles)} PDFs + {len(garbled_articles)} garbled)")
    print("=" * 60)

    corrections = []
    processed = 0
    failed = 0

    for idx, (article_id, file_name, file_path) in enumerate(all_articles, 1):
        # Resolve file path
        if file_path.startswith("images/"):
            full_path = IMAGE_DIR / file_path[7:]
        else:
            full_path = IMAGE_DIR / file_path

        if not full_path.exists():
            print(f"[{idx}/{total}] ✗ ID {article_id}: FILE NOT FOUND")
            failed += 1
            continue

        print(f"[{idx}/{total}] Processing ID {article_id}: {file_name}...", end=" ", flush=True)

        # Extract text with Claude
        corrected_text = extract_text_with_claude(full_path)

        if corrected_text:
            # Update database
            cursor.execute("""
                UPDATE articles
                SET parsed_text = ?
                WHERE id = ?
            """, (corrected_text, article_id))
            conn.commit()

            processed += 1
            text_preview = corrected_text[:100].replace("\n", " ")
            print(f"✓ ({len(corrected_text)} chars)")

            corrections.append({
                "id": article_id,
                "file_name": file_name,
                "status": "corrected",
                "text_length": len(corrected_text),
                "preview": text_preview
            })
        else:
            failed += 1
            print(f"✗ FAILED")
            corrections.append({
                "id": article_id,
                "file_name": file_name,
                "status": "failed"
            })

    conn.close()

    # Save report
    report = {
        "total_processed": total,
        "successful": processed,
        "failed": failed,
        "corrections": corrections
    }

    with open("ai_correction_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 60)
    print(f"Complete! Corrected {processed}/{total} articles")
    print(f"Failed: {failed}")
    print(f"Report saved to: ai_correction_report.json")

if __name__ == "__main__":
    main()
