#!/usr/bin/env python3
import sqlite3
import base64
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

DB_PATH = Path('archive.db')
PROJECT_DIR = Path('.')
FOLDER_NAME = '2007 Newest@Top'
IMAGES_DIR = PROJECT_DIR / 'images' / FOLDER_NAME

client = Anthropic()
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get next ID
cursor.execute('SELECT MAX(id) FROM articles')
max_id = cursor.fetchone()[0]
next_id = (max_id or 0) + 1

missing_files = [
    'img20260915_12183207.jpg',
    'img20260915_12292764.jpg',
    'img20260915_12300586.jpg',
    'img20260915_12342115.jpg',
    'img20260915_12351154.jpg'
]

print(f'Importing {len(missing_files)} missing 2007 files...')

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
print(f'\n✓ Successfully imported 5 missing 2007 articles')

conn.close()
