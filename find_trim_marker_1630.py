#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('SELECT parsed_text FROM articles WHERE id = 1630')
result = cursor.fetchone()
text = result[0]

# Look for the main article
search_text = "An option to wait and watch"

if search_text in text:
    print(f'Found: "{search_text}"')
    idx = text.find(search_text)
    line_start = text.rfind('\n', 0, idx)
    if line_start != -1:
        idx = line_start + 1
    else:
        idx = 0

    kept = text[idx:].strip()
    print(f'Will keep from this point onwards')
    print(f'Original: {len(text)} chars')
    print(f'Will keep: {len(kept)} chars')
    print(f'Will remove: {len(text) - len(kept)} chars')
    print()
    print('Preview of kept text:')
    print('-' * 80)
    print(kept[:400])
    print('-' * 80)
else:
    print(f'"{search_text}" not found')
    print('First 500 chars of article:')
    print(text[:500])

conn.close()
