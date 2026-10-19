#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path('archive.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check if topic column already exists
cursor.execute("PRAGMA table_info(articles)")
columns = [column[1] for column in cursor.fetchall()]

if 'topic' not in columns:
    cursor.execute('ALTER TABLE articles ADD COLUMN topic TEXT')
    conn.commit()
    print('Added topic column to articles table')
else:
    print('Topic column already exists')

conn.close()
