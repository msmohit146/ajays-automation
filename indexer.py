import os
import re
import sqlite3
import numpy as np
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import easyocr
import cv2

DB_NAME = "archive.db"
ROOT_DIR = "images"

reader = easyocr.Reader(['en'], gpu=False, verbose=False)

def preprocess_image(image_path):
    """Preprocess image to improve OCR accuracy"""
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)

    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)

    # Apply slight blur to reduce noise
    img = img.filter(ImageFilter.MedianFilter(size=3))

    return img

def extract_text_ocr(image_path):
    """Extract text using EasyOCR with improved preprocessing"""
    try:
        img = preprocess_image(image_path)
        img_array = np.array(img)
    except:
        return ""

    if img_array.size == 0:
        return ""

    # Convert to BGR for cv2 if needed
    if len(img_array.shape) == 2:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
    elif img_array.shape[2] == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)

    # Run EasyOCR with text detection
    try:
        results = reader.readtext(img_array, detail=1)
    except Exception:
        return ""

    if not results:
        return ""

    # Sort by Y position (top to bottom), then X (left to right)
    sorted_results = sorted(results, key=lambda r: (r[0][0][1], r[0][0][0]))

    # Group by line (Y coordinate)
    lines = []
    current_line = []
    last_y = None

    for detection in sorted_results:
        bbox = detection[0]
        text = detection[1]
        confidence = detection[2]

        if confidence < 0.25:  # Skip very low confidence
            continue

        y_pos = bbox[0][1]

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
