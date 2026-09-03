import os
import re
import sqlite3
import cv2
import numpy as np
import pytesseract
from PIL import Image

# Local Tesseract executable fallback
if os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

DB_NAME = "archive.db"
ROOT_DIR = "ajays"

def preprocess_and_ocr_columns(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return ""

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Upscale low-res scans
    h, w = gray.shape
    if h < 1200 or w < 1200:
        gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    # Convert to high contrast to remove yellow paper aging
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Vertical-only kernel (2, 25) prevents merging text horizontally across column gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 25))
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    # Find individual vertical text column boxes
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_h, img_w = gray.shape
    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw > 30 and bh > 40 and (bw * bh) > (img_w * img_h * 0.003):
            boxes.append((x, y, bw, bh))

    # Tight 50px binning sorts strictly left-to-right (Column 1 -> Column 2 -> Column 3)
    boxes = sorted(boxes, key=lambda b: (b[0] // 50, b[1]))

    extracted_text = []
    for x, y, bw, bh in boxes:
        crop = gray[y:y+bh, x:x+bw]
        text = pytesseract.image_to_string(crop, config='--psm 6 --oem 3')
        if len(text.strip()) > 10:
            extracted_text.append(text.strip())

    if not extracted_text:
        return pytesseract.image_to_string(gray, config='--psm 3 --oem 3').strip()

    raw_combined = "\n\n".join(extracted_text)
    clean_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', raw_combined)
    clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)
    return clean_text.strip()

def build_database():
    conn = sqlite3.connect(DB_NAME)
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
    cursor.execute('DELETE FROM articles')

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
                text = preprocess_and_ocr_columns(full_path)

                cursor.execute('''
                    INSERT INTO articles (file_name, folder_name, file_path, parsed_text)
                    VALUES (?, ?, ?, ?)
                ''', (file, folder_name, rel_path, text))
                count += 1

    conn.commit()
    conn.close()
    print(f"Indexing complete! {count} files processed into {DB_NAME}.")

if __name__ == "__main__":
    build_database()