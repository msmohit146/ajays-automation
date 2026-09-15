import os
import re
import sqlite3
import pytesseract
from PIL import Image, ImageEnhance

if os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

DB_NAME = "archive.db"
ROOT_DIR = "images"

def detect_and_extract_columns(img):
    """Detect columns and extract text from each column separately"""
    # Convert to grayscale if needed
    if img.mode != 'L':
        gray_img = img.convert('L')
    else:
        gray_img = img

    w, h = gray_img.size

    # Enhance contrast for better column detection
    enhancer = ImageEnhance.Contrast(gray_img)
    gray_img = enhancer.enhance(2)

    # Simple column detection: find vertical white spaces
    # Get horizontal projection (sum of pixels in each column)
    pixels = gray_img.load()
    col_sums = [0] * w

    for x in range(w):
        for y in range(h):
            # Count white pixels (>200)
            if pixels[x, y] > 200:
                col_sums[x] += 1

    # Find column boundaries (where white space is >50% of height)
    threshold = h * 0.5
    in_column = False
    columns = []
    col_start = 0

    for x in range(w):
        if col_sums[x] < threshold and not in_column:
            col_start = x
            in_column = True
        elif col_sums[x] >= threshold and in_column:
            if x - col_start > w * 0.15:  # Only consider columns >15% width
                columns.append((col_start, x))
            in_column = False

    if in_column:
        columns.append((col_start, w))

    # Extract text from each column
    if not columns or len(columns) == 1:
        # No clear column structure, use whole page
        return pytesseract.image_to_string(gray_img, config='--psm 1 --oem 3')

    extracted_text = []
    for col_start, col_end in columns:
        # Crop column with small margin
        margin = max(5, int((col_end - col_start) * 0.02))
        col_left = max(0, col_start - margin)
        col_right = min(w, col_end + margin)

        col_crop = gray_img.crop((col_left, 0, col_right, h))

        # Extract text from column
        col_text = pytesseract.image_to_string(col_crop, config='--psm 3 --oem 3')

        if col_text.strip():
            extracted_text.append(col_text.strip())

    return "\n\n".join(extracted_text) if extracted_text else pytesseract.image_to_string(gray_img, config='--psm 1 --oem 3')

def extract_text_tesseract(image_path):
    """Extract text using Tesseract with smart column detection"""
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

    # Try column-aware extraction first
    text = detect_and_extract_columns(img)

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