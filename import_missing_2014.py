#!/usr/bin/env python3
import sqlite3
import base64
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

DB_PATH = Path('archive.db')
PROJECT_DIR = Path('.')
FOLDER_NAME = '2014- Newest @Top'
IMAGES_DIR = PROJECT_DIR / 'images' / FOLDER_NAME

client = Anthropic()
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('SELECT MAX(id) FROM articles')
max_id = cursor.fetchone()[0]
next_id = (max_id or 0) + 1

missing_files = [
    'Document_2026-09-13_153254.jpg',
    'Document_2026-09-13_154107-002.jpg',
    'Document_2026-09-13_154555-002.jpg',
    'Document_2026-09-13_155014-002.jpg',
    'File name.jpg'
]

print(f'Importing {len(missing_files)} missing 2014 files...')

for filename in missing_files:
    jpg_file = IMAGES_DIR / filename
    print(f'\nProcessing: {filename}')

    with open(jpg_file, 'rb') as f:
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
                        'text': 'Extract all text from this image. Provide clean, readable text.'
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

    file_path = str(PROJECT_DIR / 'images' / FOLDER_NAME / filename)

    cursor.execute('''
        INSERT INTO articles (id, file_name, folder_name, file_path, parsed_text, image_rotation)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (next_id, filename, FOLDER_NAME, file_path, extracted_text, 0))

    print(f'  ID {next_id}: Extracted {len(extracted_text)} chars')
    next_id += 1

conn.commit()
print(f'\n✓ Successfully imported 5 missing 2014 articles')

conn.close()
