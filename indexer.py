import os
import re
import sqlite3
import numpy as np
from PIL import Image, ImageOps
import keras_ocr

DB_NAME = "archive.db"
ROOT_DIR = "images"

pipeline = keras_ocr.pipeline.Pipeline()

def extract_text_ocr(image_path):
    """Extract text using Keras-OCR with proper reading order"""
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        img_array = np.array(img)
    except:
        return ""

    if img_array.size == 0:
        return ""

    # Run Keras-OCR
    try:
        images = [img_array]
        predictions = pipeline.recognize(images)
    except Exception as e:
        return ""

    if not predictions or not predictions[0]:
        return ""

    predictions = predictions[0]

    # Sort by Y position (top to bottom), then X (left to right)
    sorted_preds = sorted(predictions, key=lambda p: (p[1][0][1], p[1][0][0]))

    # Group by line (Y coordinate)
    lines = []
    current_line = []
    last_y = None

    for text, box in sorted_preds:
        y_pos = box[0][1]  # Top Y of bounding box

        # If Y position changed significantly, it's a new line
        if last_y is not None and abs(y_pos - last_y) > 20:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = []

        current_line.append(text)
        last_y = y_pos

    if current_line:
        lines.append(' '.join(current_line))

    text = '\n'.join(lines)

    if not text.strip():
        return ""

    # Clean up text
    clean_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)  # Fix hyphenation
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)  # Normalize newlines
    clean_text = re.sub(r'[ \t]{2,}', ' ', clean_text)  # Fix multiple spaces
    clean_text = re.sub(r'\s+$', '', clean_text, flags=re.MULTILINE)  # Remove trailing

    return clean_text.strip()

def build_database():
    temp_db = "archive_temp.db"

    if os.path.exists(temp_db):
        try:
            os.remove(temp_db)
        except:
            pass

    conn = sqlite3.connect(temp_db, timeout=30)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            folder_name TEXT,
            file_path TEXT,
            parsed_text TEXT
        )
    ''')

    count = 0
    for root, dirs, files in os.walk(ROOT_DIR):
        folder_name = os.path.basename(root)
        if folder_name == ROOT_DIR:
            folder_name = "Root"

        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                full_path = os.path.join(root, file)
                rel_path = os.path.normpath(full_path).replace("\\", "/")

                print(f"Indexing: {rel_path}")
                text = extract_text_ocr(full_path)

                cursor.execute('''
                    INSERT INTO articles (file_name, folder_name, file_path, parsed_text)
                    VALUES (?, ?, ?, ?)
                ''', (file, folder_name, rel_path, text))
                count += 1
                if count % 10 == 0:
                    conn.commit()
                    print(f"Progress: {count} files processed...")

    conn.commit()
    conn.close()

    import shutil
    try:
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
    except:
        pass

    shutil.move(temp_db, DB_NAME)
    print(f"Indexing complete! {count} files processed into {DB_NAME}.")

if __name__ == "__main__":
    build_database()
