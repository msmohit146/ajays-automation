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

cursor.execute('SELECT file_path FROM articles WHERE id = 1913')
file_path_str = cursor.fetchone()[0]
image_path = PROJECT_DIR / file_path_str

print(f'Extracting Ajay\'s column from article 1913...')

with open(image_path, 'rb') as f:
    image_data = base64.standard_b64encode(f.read()).decode('utf-8')

message = client.messages.create(
    model='claude-sonnet-5-5',
    max_tokens=1500,
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
                    'text': 'This image shows three columns with different people discussing mutual funds. Extract ONLY the rightmost column about Ajay Srinivasan (Prudential-ICICI AMC). Include his name, title, and his complete quote/commentary.'
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
print('\nExtracted text:')
print('='*80)
print(extracted_text)
print('='*80)

# Update database
cursor.execute('UPDATE articles SET parsed_text = ? WHERE id = 1913', (extracted_text,))
conn.commit()
print(f'\nSUCCESS: Article 1913 updated')

conn.close()
