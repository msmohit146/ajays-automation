#!/usr/bin/env python3
import sqlite3
import base64
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

DB_PATH = Path('archive.db')
PROJECT_DIR = Path('.')
FOLDER_NAME = '2003-2004/2004'
IMAGES_DIR = PROJECT_DIR / 'images' / FOLDER_NAME

client = Anthropic()
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get the next available ID
cursor.execute('SELECT MAX(id) FROM articles')
max_id = cursor.fetchone()[0]
next_id = (max_id or 0) + 1

print(f'Starting import with ID: {next_id}')

# Get JPG files only
jpg_files = sorted([f for f in IMAGES_DIR.glob('*.jpg') if f.is_file()])
print(f'Found {len(jpg_files)} JPG files to import')

imported_count = 0
for jpg_file in jpg_files:
    print(f'\nProcessing: {jpg_file.name}')

    # Extract text using vision API
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
                        'text': 'Extract all text from this image. Provide clean, readable text without any formatting or comments.'
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

    # Calculate relative file path
    file_path = f'images/{FOLDER_NAME}/{jpg_file.name}'

    # Insert into database
    cursor.execute('''
        INSERT INTO articles (id, file_name, folder_name, file_path, parsed_text, image_rotation)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (next_id, jpg_file.name, FOLDER_NAME, file_path, extracted_text, 0))

    print(f'  ID {next_id}: Extracted {len(extracted_text)} characters')
    imported_count += 1
    next_id += 1

conn.commit()
print(f'\n✓ Successfully imported {imported_count} articles')
print(f'Article IDs: {next_id - imported_count} to {next_id - 1}')

conn.close()
