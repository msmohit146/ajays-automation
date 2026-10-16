#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Update article 2041 to have no rotation
cursor.execute(
    "UPDATE articles SET image_rotation = 0 WHERE id = 2041"
)
conn.commit()

# Verify
cursor.execute("SELECT id, file_name, image_rotation FROM articles WHERE id = 2041")
result = cursor.fetchone()
print(f"Updated article {result[0]}: {result[1]}")
print(f"New rotation: {result[2]} degrees")

conn.close()
