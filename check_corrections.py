import sqlite3
from pathlib import Path

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check a few PDF articles
print("=== CHECKING PDF ARTICLES ===")
cursor.execute("SELECT id, file_name, LENGTH(parsed_text) as text_len FROM articles WHERE id IN (1569, 1575, 1581) ORDER BY id")
for article_id, file_name, text_len in cursor.fetchall():
    cursor.execute("SELECT parsed_text FROM articles WHERE id = ?", (article_id,))
    text = cursor.fetchone()[0]
    preview = text[:100] if text else "NO TEXT"
    print(f"ID {article_id}: {file_name}")
    print(f"  Length: {text_len} chars")
    print(f"  Preview: {preview}...")
    print()

# Check garbled articles
print("=== CHECKING GARBLED ARTICLES ===")
cursor.execute("SELECT id, file_name, LENGTH(parsed_text) as text_len FROM articles WHERE id IN (150, 1541, 1542) ORDER BY id")
for article_id, file_name, text_len in cursor.fetchall():
    cursor.execute("SELECT parsed_text FROM articles WHERE id = ?", (article_id,))
    text = cursor.fetchone()[0]
    preview = text[:100] if text else "NO TEXT"
    print(f"ID {article_id}: {file_name}")
    print(f"  Length: {text_len} chars")
    print(f"  Preview: {preview}...")
    print()

conn.close()
