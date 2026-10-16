#!/usr/bin/env python3
import sqlite3
import base64
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

DB_PATH = Path('archive.db')
client = Anthropic()
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('SELECT file_path FROM articles WHERE id = 2033')
file_path_str = cursor.fetchone()[0]
image_path = Path(file_path_str)

print(f'Extracting text from article 2033...')

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

print(f'Extracted {len(extracted_text)} characters')

cursor.execute('UPDATE articles SET parsed_text = ? WHERE id = 2033', (extracted_text,))
conn.commit()
print(f'SUCCESS: Article 2033 updated')

conn.close()
