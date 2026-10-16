import sqlite3
from pathlib import Path
import json
import sys

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find PDF entries
print("=== PDF ARTICLES TO PROCESS ===")
cursor.execute("""
    SELECT id, file_name, file_path, parsed_text
    FROM articles
    WHERE file_path LIKE '%.pdf%' OR file_name LIKE '%.pdf%'
    ORDER BY id
""")
pdf_articles = cursor.fetchall()
print(f"Found {len(pdf_articles)} PDF articles")

# Find garbled articles
print("\n=== GARBLED OCR ARTICLES TO PROCESS ===")
garbled_ids = [150, 151, 152, 153, 154, 155, 156, 676, 1541, 1542, 1543, 1544, 1545, 1546, 1548, 1549, 2022, 2051]
cursor.execute("SELECT id, file_name, file_path FROM articles WHERE id IN ({})".format(
    ",".join("?" * len(garbled_ids))
), garbled_ids)
garbled_articles = cursor.fetchall()
print(f"Found {len(garbled_articles)} articles with garbled OCR")

print("\n=== CHECKING FILE EXISTENCE ===")

# Check which PDFs exist
pdf_found = 0
pdf_missing = 0
for article_id, file_name, file_path, _ in pdf_articles:
    full_path = Path("images") / file_path if not file_path.startswith("images/") else Path(file_path)
    if full_path.exists():
        pdf_found += 1
        print(f"✓ ID {article_id}: {file_name} EXISTS")
    else:
        pdf_missing += 1
        print(f"✗ ID {article_id}: {file_name} MISSING ({full_path})")

# Check garbled articles
garbled_found = 0
for article_id, file_name, file_path in garbled_articles:
    full_path = Path("images") / file_path if not file_path.startswith("images/") else Path(file_path)
    if full_path.exists():
        garbled_found += 1
        print(f"✓ ID {article_id}: {file_name} EXISTS")
    else:
        print(f"✗ ID {article_id}: {file_name} MISSING")

print(f"\nSummary:")
print(f"  PDFs: {pdf_found} found, {pdf_missing} missing")
print(f"  Garbled articles: {garbled_found} found, {len(garbled_articles) - garbled_found} missing")

conn.close()

if pdf_found > 0 or garbled_found > 0:
    print(f"\n→ Ready to process {pdf_found + garbled_found} articles with Claude AI")
    print("→ This will extract correct OCR text from images/PDFs")
