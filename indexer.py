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
ROOT_DIR = "images"

def deskew_image(gray):
    """Auto-rotate image to correct skew"""
    coords = np.column_stack(np.where(gray > 127))
    if len(coords) < 100:
        return gray

    angle = cv2.minAreaRect(coords)[2]
    if angle < -45:
        angle = 90 + angle

    if abs(angle) > 2:
        h, w = gray.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        gray = cv2.warpAffine(gray, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    return gray

def preprocess_and_ocr_columns(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return ""

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Auto-deskew rotated images
    gray = deskew_image(gray)

    # Upscale low-res scans
    h, w = gray.shape
    if h < 1200 or w < 1200:
        gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    # Denoise
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Adaptive thresholding for better contrast on aged paper
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)

    # Vertical-only kernel prevents merging text horizontally across column gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 20))
    dilated = cv2.dilate(thresh, kernel, iterations=1)

    # Find individual vertical text column boxes
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_h, img_w = gray.shape
    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        # Filter by size - must be substantial text blocks
        if bw > 50 and bh > 80 and (bw * bh) > (img_w * img_h * 0.001):
            boxes.append((x, y, bw, bh))

    # Sort left-to-right, then top-to-bottom within columns (100px binning)
    boxes = sorted(boxes, key=lambda b: (b[0] // 100, b[1]))

    extracted_text = []
    for x, y, bw, bh in boxes:
        crop = gray[y:y+bh, x:x+bw]
        # PSM 6: single text block, OEM 3: legacy + neural
        text = pytesseract.image_to_string(crop, config='--psm 6 --oem 3')
        cleaned = text.strip()
        if len(cleaned) > 15:
            extracted_text.append(cleaned)

    if not extracted_text:
        # Fallback: read entire page
        return pytesseract.image_to_string(gray, config='--psm 3 --oem 3').strip()

    raw_combined = "\n\n".join(extracted_text)
    # Fix hyphenation
    clean_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', raw_combined)
    # Normalize whitespace
    clean_text = re.sub(r'\n\s*\n+', '\n\n', clean_text)
    # Remove extra spaces
    clean_text = re.sub(r' +', ' ', clean_text)
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
                text = preprocess_and_ocr_columns(full_path)

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