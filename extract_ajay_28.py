#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path('archive.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('SELECT parsed_text FROM articles WHERE id = 28')
text = cursor.fetchone()[0]

# Find where Ajay's section starts
search_text = 'Ajay Srinivasan'
idx = text.find(search_text)

if idx != -1:
    # Go back to find section start (look for line break before the name)
    line_start = text.rfind('\n', 0, idx)
    if line_start != -1:
        start_idx = line_start + 1
    else:
        start_idx = 0

    ajay_text = text[start_idx:].strip()

    print(f'PREVIEW - Article 28 (Ajay only)')
    print('=' * 80)
    print(f'Original: {len(text)} chars')
    print(f'Keeping: {len(ajay_text)} chars')
    print()
    print(ajay_text)
    print()
    print('=' * 80)
    print('CONFIRM: Apply this change? (y/n)')

    response = input().strip().lower()

    if response == 'y':
        cursor.execute('UPDATE articles SET parsed_text = ? WHERE id = 28', (ajay_text,))
        conn.commit()
        print('✓ Updated successfully')
    else:
        print('Cancelled')

conn.close()
