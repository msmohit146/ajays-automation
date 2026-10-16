import sqlite3
from pathlib import Path

db_path = Path("archive.db")
IMAGE_DIR = Path("images")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find all converted PDF images
pdf_conversions = {
    1569: "2003-2004/2004/Document_2026-08-15_101015-001.jpg",
    1570: "2003-2004/2004/Document_2026-08-15_103324-001.jpg",
    1571: "2003-2004/2004/Document_2026-08-15_103615-001.jpg",
    1572: "2005/2005-001.jpg",
    1573: "2005/Document_2026-08-15_111302-001.jpg",
    1574: "2008- Newest @Top/2008-001.jpg",
    1575: "2008- Newest @Top/Document_2026-09-15_121959-001.jpg",
    1576: "2008- Newest @Top/Document_2026-09-15_122545-001.jpg",
    1577: "2008- Newest @Top/Document_2026-09-15_123147-001.jpg",
    1578: "2008- Newest @Top/Document_2026-09-15_123835-001.jpg",
    1579: "2008- Newest @Top/Document_2026-09-15_124130-001.jpg",
    1580: "2008- Newest @Top/Document_2026-09-15_124306-001.jpg",
    1581: "2010- Newest @Top/Document_2026-09-15_113049-001.jpg",
    1582: "2010- Newest @Top/Document_2026-09-15_114651-001.jpg",
    1583: "2010- Newest @Top/Document_2026-09-15_115312-001.jpg",
    1584: "2010- Newest @Top/Document_2026-09-15_115721-001.jpg",
    1585: "2010- Newest @Top/Document_2026-09-15_115934-001.jpg",
    1586: "2010- Newest @Top/Document_2026-09-15_120637-001.jpg",
    1587: "2010- Newest @Top/Document_2026-09-15_121014-001.jpg",
    1588: "2011- Newest @Top/Document_2026-09-13_164007-001.jpg",
}

count = 0
for article_id, relative_path in pdf_conversions.items():
    new_path = f"images/{relative_path}"
    new_filename = Path(relative_path).name

    # Verify file exists
    full_path = IMAGE_DIR / relative_path
    if full_path.exists():
        cursor.execute("""
            UPDATE articles
            SET file_path = ?, file_name = ?
            WHERE id = ?
        """, (new_path, new_filename, article_id))
        count += 1

conn.commit()
conn.close()

print(f"Updated {count} articles with converted image paths")
print("Note: Run OCR extraction agent next to fix remaining articles")
