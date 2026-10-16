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

if search_text in text:
    print(f'Found: "{search_text}"')
    idx = text.find(search_text)
    line_start = text.rfind('\n', 0, idx)
    if line_start != -1:
        idx = line_start + 1
    else:
        idx = 0

    kept = text[idx:].strip()
    print(f'\nVERIFICATION PREVIEW')
    print('=' * 80)
    print(f'Original: {len(text)} chars')
    print(f'Will keep: {len(kept)} chars')
    print(f'Will remove: {len(text) - len(kept)} chars')
    print()
    print('Preview of kept text (first 400 chars):')
    print('-' * 80)
    print(kept[:400])
    print('-' * 80)
else:
    print(f'"{search_text}" not found')
    print('First 500 chars:')
    print(text[:500])

conn.close()
