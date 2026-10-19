#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path('archive.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check if needs_rescan column already exists
cursor.execute("PRAGMA table_info(articles)")
columns = [column[1] for column in cursor.fetchall()]

if 'needs_rescan' not in columns:
    cursor.execute('ALTER TABLE articles ADD COLUMN needs_rescan INTEGER DEFAULT 0')
    conn.commit()
    print('Added needs_rescan column to articles table')
else:
    print('needs_rescan column already exists')

# Mark article 1716 for re-scanning
cursor.execute('UPDATE articles SET needs_rescan = 1 WHERE id = 1716')
conn.commit()
print('Marked article 1716 for re-scanning')

conn.close()
