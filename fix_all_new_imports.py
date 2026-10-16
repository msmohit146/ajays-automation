#!/usr/bin/env python3
import sqlite3
import base64
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

DB_PATH = Path('archive.db')
PROJECT_DIR = Path('.')
client = Anthropic()
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get all newly imported articles (excluding 2011 which was already fixed)
# 2004: 2361-2373, 2007: 2374-2378, 2009: 2379-2383, 2014: 2397-2401
article_ranges = [
    (2361, 2373),  # 2004
    (2374, 2378),  # 2007
    (2379, 2383),  # 2009
    (2397, 2401)   # 2014
]

total_articles = sum(end - start + 1 for start, end in article_ranges)
print(f'Fixing text for {total_articles} newly imported articles...')

count = 0
for start_id, end_id in article_ranges:
    cursor.execute('SELECT id, file_path FROM articles WHERE id BETWEEN ? AND ? ORDER BY id', (start_id, end_id))
    articles = cursor.fetchall()

    for article_id, file_path in articles:
        image_path = Path(file_path)
        print(f'\n[{count+1}/{total_articles}] ID {article_id}: {image_path.name}')
        count += 1

        try:
            with open(image_path, 'rb') as f:
                image_data = base64.standard_b64encode(f.read()).decode('utf-8')

            message = client.messages.create(
                model='claude-sonnet-5-5',
                max_tokens=2000,
                messages=[
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'image',
                                'source': {
                                    'type': 'base64',
                                    'media_type': 'image/jpeg',
                                    'data': image_data,
                                },
                            },
                            {
                                'type': 'text',
                                'text': 'Extract all text from this image. Provide clean, readable text without any formatting.'
                            }
                        ],
                    }
                ],
            )

            extracted_text = ""
            for block in message.content:
                if hasattr(block, 'text'):
                    extracted_text += block.text

            if not extracted_text.strip():
                extracted_text = "[No readable text found]"

            cursor.execute('UPDATE articles SET parsed_text = ? WHERE id = ?', (extracted_text, article_id))
            print(f'  Extracted {len(extracted_text)} chars')
        except Exception as e:
            print(f'  Error: {e}')

conn.commit()
print(f'\n✓ Successfully fixed {total_articles} articles')

conn.close()
