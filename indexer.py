import os
import re
import sqlite3
import pytesseract
from PIL import Image

if os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

DB_NAME = "archive.db"
ROOT_DIR = "images"

def extract_text_tesseract(image_path):
    """Extract text using Tesseract with preprocessing via PIL"""
    try:
        img = Image.open(image_path)
    except:
        return ""

    # Upscale low-res images
    w, h = img.size
    if h < 1200 or w < 1200:
        new_w = w * 2
        new_h = h * 2
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # Convert to grayscale
    if img.mode != 'L':
        img = img.convert('L')

    # Use Tesseract with automatic page segmentation
    text = pytesseract.image_to_string(img, config='--psm 1 --oem 3')

    if not text.strip():
        # Fallback: try with different PSM
        text = pytesseract.image_to_string(img, config='--psm 3 --oem 3')

    # Clean up text
    clean_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)  # Fix hyphenation
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
                text = extract_text_tesseract(full_path)

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