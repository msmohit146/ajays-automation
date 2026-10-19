#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path('archive.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Find articles that mention both Ajay AND ICICI
cursor.execute('''
    SELECT id, file_name, parsed_text
    FROM articles
    WHERE parsed_text LIKE ? AND parsed_text LIKE ?
    ORDER BY id
''', ('%Ajay%', '%ICICI%'))

articles = cursor.fetchall()

print(f'Found {len(articles)} articles with both Ajay and ICICI')
print('=' * 80)

for article_id, file_name, text in articles[:20]:  # Show first 20
    print(f'\nArticle ID: {article_id}')
    print(f'File: {file_name}')
    print(f'Text length: {len(text)} chars')

    # Look for Ajay section
    if 'Ajay Srinivasan' in text:
        idx = text.find('Ajay Srinivasan')
        preview_start = max(0, idx - 50)
        preview_end = min(len(text), idx + 200)
        print(f'Preview: ...{text[preview_start:preview_end]}...')
    print('-' * 80)

print(f'\nTotal articles with Ajay + ICICI: {len(articles)}')
conn.close()
