#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Search by file name
cursor.execute(
    "SELECT id, file_name, folder_name, image_rotation FROM articles WHERE file_name LIKE ?",
    ('%img20260815_10064133%',)
)
result = cursor.fetchone()

if result:
    print(f'Found article ID: {result[0]}')
    print(f'File: {result[1]}')
    print(f'Folder: {result[2]}')
    print(f'Current rotation: {result[3]}')
else:
    print('Not found by exact file name, searching 2006 folder articles...')
    cursor.execute(
        "SELECT id, file_name, folder_name, image_rotation FROM articles WHERE folder_name LIKE ? ORDER BY id DESC LIMIT 5",
        ('%2006%',)
    )
    results = cursor.fetchall()
    for r in results:
        print(f'ID: {r[0]}, File: {r[1][:50]}, Rotation: {r[3]}')

conn.close()
