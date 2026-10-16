import sqlite3
from pathlib import Path

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all PDF and garbled article IDs
pdf_ids = []
cursor.execute("SELECT id FROM articles WHERE file_path LIKE '%.pdf%' OR file_name LIKE '%.pdf%'")
pdf_ids = [row[0] for row in cursor.fetchall()]

garbled_ids = [150, 151, 152, 153, 154, 155, 156, 676, 1541, 1542, 1543, 1544, 1545, 1546, 1548, 1549, 2022, 2051]

all_ids = sorted(set(pdf_ids + garbled_ids))
total = len(all_ids)

# Check how many have proper text (length > 100)
corrected = 0
empty = 0
short = 0

for article_id in all_ids:
    cursor.execute("SELECT LENGTH(parsed_text) FROM articles WHERE id = ?", (article_id,))
    result = cursor.fetchone()
    if result:
        text_len = result[0]
        if text_len is None or text_len == 0:
            empty += 1
        elif text_len < 100:
            short += 1
        else:
            corrected += 1

print(f"Total articles to correct: {total}")
print(f"Successfully corrected (>100 chars): {corrected}")
print(f"Empty text: {empty}")
print(f"Short text (<100 chars): {short}")
print(f"\nCompletion rate: {corrected}/{total} = {100*corrected/total:.1f}%")

# Show any that weren't corrected
if empty > 0 or short > 0:
    print("\nArticles needing attention:")
    for article_id in all_ids:
        cursor.execute("SELECT file_name, LENGTH(parsed_text) FROM articles WHERE id = ?", (article_id,))
        file_name, text_len = cursor.fetchone()
        if text_len is None or text_len < 100:
            print(f"  ID {article_id}: {file_name} ({text_len or 0} chars)")

conn.close()
