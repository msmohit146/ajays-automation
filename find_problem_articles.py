import sqlite3
from pathlib import Path
import re

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find PDF entries (should be images, not PDFs)
print("=== PDF ENTRIES ===")
cursor.execute("""
    SELECT id, file_name, folder_name, file_path
    FROM articles
    WHERE file_path LIKE '%.pdf%' OR file_name LIKE '%.pdf%'
    ORDER BY id
""")
pdf_results = cursor.fetchall()
print(f"Found {len(pdf_results)} PDF entries:\n")
for article_id, file_name, folder_name, file_path in pdf_results[:20]:
    print(f"ID {article_id}: {file_name} ({folder_name})")

# Find articles with garbled/corrupted OCR text
print("\n\n=== ARTICLES WITH GARBLED OCR ===")
cursor.execute("SELECT id, file_name, parsed_text FROM articles ORDER BY id")
all_articles = cursor.fetchall()

garbled_articles = []
for article_id, file_name, parsed_text in all_articles:
    if not parsed_text or len(parsed_text) < 50:
        continue

    # Check for signs of garbled text:
    # - Many non-ASCII characters
    # - Repeated strange patterns
    # - Incoherent words

    text = parsed_text[:500]

    # Count non-ASCII characters
    non_ascii = sum(1 for c in text if ord(c) > 127)
    non_ascii_ratio = non_ascii / len(text) if text else 0

    # Check for patterns that indicate bad OCR
    if non_ascii_ratio > 0.2:  # More than 20% non-ASCII
        garbled_articles.append((article_id, file_name, non_ascii_ratio))
    elif re.search(r'[a-z]{15,}', text) and non_ascii_ratio > 0.05:  # Long nonsense words
        garbled_articles.append((article_id, file_name, non_ascii_ratio))

print(f"Found {len(garbled_articles)} articles with potentially garbled OCR:\n")
for article_id, file_name, ratio in garbled_articles[:20]:
    print(f"ID {article_id}: {file_name} (non-ASCII ratio: {ratio:.1%})")

conn.close()

print(f"\n\nSummary:")
print(f"  PDF entries: {len(pdf_results)}")
print(f"  Garbled OCR articles: {len(garbled_articles)}")
