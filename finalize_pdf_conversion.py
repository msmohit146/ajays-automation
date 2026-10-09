import sqlite3
from pathlib import Path
import json

db_path = Path("archive.db")
IMAGE_DIR = Path("images")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all current PDF articles
cursor.execute("""
    SELECT id, file_name, file_path
    FROM articles
    WHERE file_path LIKE '%.pdf%' OR file_name LIKE '%.pdf%'
    ORDER BY id
""")
pdf_articles = cursor.fetchall()

updates = []

for article_id, file_name, file_path in pdf_articles:
    # Find the converted image for this PDF
    if file_path.startswith("images/"):
        pdf_path = file_path[7:]
    else:
        pdf_path = file_path

    # Construct the expected image path (first page, -001)
    pdf_stem = Path(pdf_path).stem
    pdf_dir = Path(pdf_path).parent

    # Search for the converted image
    image_pattern = f"{pdf_stem}-001.jpg"
    full_search_path = IMAGE_DIR / pdf_dir / image_pattern

    if full_search_path.exists():
        new_path = f"images/{pdf_dir}/{image_pattern}"
        new_filename = image_pattern

        cursor.execute("""
            UPDATE articles
            SET file_path = ?, file_name = ?
            WHERE id = ?
        """, (new_path, new_filename, article_id))

        updates.append({
            "id": article_id,
            "old_file": file_name,
            "new_file": new_filename,
            "status": "converted"
        })

conn.commit()

# Get updated count
cursor.execute("SELECT COUNT(*) FROM articles")
total = cursor.fetchone()[0]

conn.close()

print(f"Updated {len(updates)} PDF articles")
print(f"Total articles in database: {total}")
print(f"PDFs are now displayable as images in Streamlit")

# Save update report
with open("pdf_conversion_finalized.json", "w") as f:
    json.dump({
        "converted": len(updates),
        "total_articles": total,
        "updates": updates
    }, f, indent=2)
