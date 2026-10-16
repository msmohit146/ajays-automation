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

# Get all 13 newly imported 2011 articles
cursor.execute('SELECT id, file_path FROM articles WHERE id BETWEEN 2384 AND 2396 ORDER BY id')
articles = cursor.fetchall()

print(f'Fixing {len(articles)} jumbled 2011 articles...')

for article_id, file_path in articles:
    image_path = Path(file_path)
    print(f'\nProcessing ID {article_id}: {image_path.name}')

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

conn.commit()
print(f'\n✓ Successfully fixed 13 jumbled 2011 articles')

conn.close()
