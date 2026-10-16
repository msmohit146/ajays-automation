#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute(
    "SELECT id, file_name, folder_name FROM articles WHERE file_name LIKE ?",
    ('%13.01.59%',)
)
result = cursor.fetchone()

if result:
    print(f'Article ID: {result[0]}')
    print(f'File: {result[1]}')
else:
    print('Not found')

conn.close()
