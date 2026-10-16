#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute(
    "SELECT id, file_name, folder_name FROM articles WHERE file_name LIKE ?",
    ('%12.57.32%',)
)
result = cursor.fetchone()

if result:
    print(f'Article ID: {result[0]}')
    print(f'File: {result[1]}')
    print(f'Folder: {result[2]}')
else:
    print('Not found by exact name, checking ABFS folder...')
    cursor.execute(
        "SELECT id, file_name, folder_name FROM articles WHERE folder_name LIKE ? ORDER BY id DESC LIMIT 10",
        ('%ABFS%',)
    )
    results = cursor.fetchall()
    for r in results:
        print(f'ID: {r[0]}, File: {r[1][:50]}, Folder: {r[2]}')

conn.close()
