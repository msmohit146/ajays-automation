#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('SELECT parsed_text FROM articles WHERE id = 1755')
result = cursor.fetchone()
text = result[0]

search_text = "Ajay Srinivasan, Deputy Chief Executive, ITC Threadneedle"
idx = text.find(search_text)
line_start = text.rfind('\n', 0, idx)
if line_start != -1:
    idx = line_start + 1
else:
    idx = 0

kept_text = text[idx:].strip()

cursor.execute('UPDATE articles SET parsed_text = ? WHERE id = 1755', (kept_text,))
conn.commit()

print(f'SUCCESS: Article 1755 updated')
print(f'  Removed: {len(text) - len(kept_text)} characters')
print(f'  Kept: {len(kept_text)} characters')

conn.close()
