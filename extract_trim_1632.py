#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('SELECT parsed_text FROM articles WHERE id = 1632')
result = cursor.fetchone()
text = result[0]

search_text = "Not the time to go backward"

if search_text in text:
    idx = text.find(search_text)
    line_start = text.rfind('\n', 0, idx)
    if line_start != -1:
        idx = line_start + 1
    else:
        idx = 0

    kept_text = text[idx:].strip()

    print(f'VERIFICATION')
    print(f'Original: {len(text)} chars')
    print(f'Will keep: {len(kept_text)} chars')
    print(f'Will remove: {len(text) - len(kept_text)} chars')

    cursor.execute('UPDATE articles SET parsed_text = ? WHERE id = 1632', (kept_text,))
    conn.commit()
    print(f'\nSUCCESS: Article 1632 updated')
else:
    print(f'Text not found')

conn.close()
