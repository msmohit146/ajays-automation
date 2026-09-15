import os
import re
import sqlite3
import pytesseract
from PIL import Image, ImageFilter, ImageOps

if os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

DB_NAME = "archive.db"
ROOT_DIR = "images"

def detect_columns(img):
    """Detect columns by analyzing white space (PIL only, no cv2)"""
    # Convert to grayscale
    if img.mode != 'L':
        gray = img.convert('L')
    else:
        gray = img

    w, h = gray.size
    pixels = gray.load()

    # Count white pixels in each column
    col_white = [0] * w
    for x in range(w):
        for y in range(h):
            if pixels[x, y] > 200:  # White pixels
                col_white[x] += 1

    # Find columns: areas with low white density indicate column gaps
    threshold = h * 0.7  # 70% threshold for gap detection
    columns = []
    in_column = False
    col_start = 0

    for x in range(w):
        is_gap = col_white[x] > threshold

        if not is_gap and not in_column:
            col_start = x
            in_column = True
        elif is_gap and in_column:
            col_width = x - col_start
            if col_width > w * 0.15:  # Column must be >15% width
                columns.append((col_start, x))
            in_column = False

    if in_column:
        columns.append((col_start, w))

    return columns if len(columns) > 1 else None

def extract_text_ocr(image_path):
    """Extract text with smart column detection (PIL + Tesseract)"""
    try:
        img = Image.open(image_path)
    except:
        return ""

    # Upscale low-res images
    w, h = img.size
    if h < 1200 or w < 1200:
        scale = 2 if h < 1200 else 1
        img = img.resize((w * scale, h * scale), Image.LANCZOS)

    # Convert to grayscale and enhance
    if img.mode != 'L':
        img = img.convert('L')

    # Enhance contrast
    img = ImageOps.autocontrast(img, cutoff=5)

    # Detect columns
    columns = detect_columns(img)

    extracted_text = []

    if columns:
        # Process each column separately
        for col_start, col_end in columns:
            # Add small margin
            margin = max(5, int((col_end - col_start) * 0.02))
            left = max(0, col_start - margin)
            right = min(img.width, col_end + margin)

            # Crop column
            col_img = img.crop((left, 0, right, img.height))

            # Extract text from column
            col_text = pytesseract.image_to_string(col_img, config='--psm 3 --oem 3')

            if col_text.strip():
                extracted_text.append(col_text.strip())

        # Join columns with double newline
        text = "\n\n".join(extracted_text)
    else:
        # No clear columns, process whole page
        text = pytesseract.image_to_string(img, config='--psm 1 --oem 3')

    if not text.strip():
        return ""

    # Clean up text
    clean_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)  # Fix hyphenation
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)  # Normalize newlines
    clean_text = re.sub(r'[ \t]{2,}', ' ', clean_text)  # Fix multiple spaces
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