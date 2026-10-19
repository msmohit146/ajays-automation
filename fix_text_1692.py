#!/usr/bin/env python3
import sqlite3
import base64
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()

DB_PATH = Path('archive.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('SELECT file_path FROM articles WHERE id = 1692')
file_path = Path(cursor.fetchone()[0])

print(f'Re-extracting text from article 1692...')
print(f'File: {file_path.name}')

with open(file_path, 'rb') as f:
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

print(f'Extracted {len(extracted_text)} chars')
print('\nPreview:')
print('-' * 80)
print(extracted_text[:600])
print('-' * 80)

cursor.execute('UPDATE articles SET parsed_text = ? WHERE id = 1692', (extracted_text,))
conn.commit()
print('\nUpdated article 1692')

conn.close()
