import os
import re
import sqlite3
import keras_ocr
from PIL import Image
import numpy as np

DB_NAME = "archive.db"
ROOT_DIR = "images"

# Initialize Keras-OCR pipeline (loads models on first run)
pipeline = keras_ocr.pipeline.Pipeline()

def extract_text_keras_ocr(image_path):
    """Extract text using Keras-OCR (better for scanned documents)"""
    try:
        # Read image
        images = [keras_ocr.tools.read(image_path)]
    except:
        return ""

    # Predict text
    try:
        prediction_groups = pipeline.recognize(images)
    except Exception as e:
        print(f"OCR error for {image_path}: {e}")
        return ""

    if not prediction_groups or not prediction_groups[0]:
        return ""

    # Extract text with positional info to maintain order
    predictions = prediction_groups[0]

    # Sort by reading order: top-to-bottom, left-to-right
    sorted_predictions = sorted(predictions, key=lambda x: (
        int(x[1][0][1]),  # y coordinate (top)
        int(x[1][0][0])   # x coordinate (left)
    ))

    # Group by lines (similar y-coordinates)
    lines = {}
    for text, box in sorted_predictions:
        y_coord = int(box[0][1])  # Top y coordinate

        # Group by approximate y position (within 20 pixels)
        line_key = round(y_coord / 20) * 20

        if line_key not in lines:
            lines[line_key] = []

        lines[line_key].append((int(box[0][0]), text))  # Store with x position

    # Build text maintaining reading order
    extracted_lines = []
    for y_key in sorted(lines.keys()):
        # Sort words in line by x position (left to right)
        words = sorted(lines[y_key], key=lambda x: x[0])
        line_text = " ".join([word[1] for word in words])

        if line_text.strip():
            extracted_lines.append(line_text.strip())

    if not extracted_lines:
        return ""

    # Join lines with newlines
    full_text = "\n".join(extracted_lines)

    # Clean up text
    clean_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', full_text)  # Fix hyphenation
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)  # Normalize newlines
    clean_text = re.sub(r'[ \t]{2,}', ' ', clean_text)  # Fix spaces
    clean_text = re.sub(r'\s+$', '', clean_text, flags=re.MULTILINE)  # Remove trailing

    return clean_text.strip()

def build_database():
    # Build in a temp database first, then move it
    temp_db = "archive_temp.db"

    # Remove old temp db if it exists
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
                text = extract_text_keras_ocr(full_path)

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

    # Replace old database with new one
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