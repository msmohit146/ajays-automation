#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path("archive.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Try rotation 270 (applies -270 degrees = 90 degrees clockwise)
cursor.execute(
    "UPDATE articles SET image_rotation = 270 WHERE id = 2041"
)
conn.commit()

cursor.execute("SELECT id, file_name, image_rotation FROM articles WHERE id = 2041")
result = cursor.fetchone()
print(f"Updated article {result[0]}: {result[1]}")
print(f"New rotation: {result[2]} degrees")

conn.close()
