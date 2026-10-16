import sqlite3
from pathlib import Path

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find the article
cursor.execute("""
    SELECT id, file_name, file_path, parsed_text
    FROM articles
    WHERE file_name LIKE '%144254%' AND folder_name = '1993'
""")
result = cursor.fetchone()
conn.close()

if result:
    article_id, file_name, file_path, parsed_text = result
    print(f"Found article:")
    print(f"  ID: {article_id}")
    print(f"  File: {file_name}")
    print(f"  Path: {file_path}")
    print(f"\nCurrent OCR text ({len(parsed_text or '')} chars):")
    print(parsed_text[:800])
    print("\n...")
else:
    print("Article not found - searching for all 1993 articles...")
    cursor = sqlite3.connect(db_path).cursor()
    cursor.execute("SELECT id, file_name FROM articles WHERE folder_name = '1993' ORDER BY id")
    for aid, fn in cursor.fetchall():
        print(f"  ID {aid}: {fn}")
