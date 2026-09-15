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
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    gray = cv2.medianBlur(gray, 3)

    # Use OTSU thresholding for better paper handling
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Morphological operations to clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    # Find text regions with horizontal kernel
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
    h_lines = cv2.dilate(thresh, h_kernel, iterations=2)

    # Find contours for text blocks
    contours, _ = cv2.findContours(h_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_h, img_w = gray.shape
    boxes = []

    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        # Filter: at least 100px wide, 30px tall, substantial area
        if bw > 100 and bh > 30 and (bw * bh) > (img_w * img_h * 0.0005):
            boxes.append((x, y, bw, bh))

    # Merge overlapping boxes
    merged_boxes = []
    for x, y, w, h in sorted(boxes, key=lambda b: (b[1], b[0])):
        merged = False
        for i, (mx, my, mw, mh) in enumerate(merged_boxes):
            # Check if boxes overlap vertically
            if not (y > my + mh or y + h < my):
                # Merge
                nx = min(x, mx)
                ny = min(y, my)
                nx2 = max(x + w, mx + mw)
                ny2 = max(y + h, my + mh)
                merged_boxes[i] = (nx, ny, nx2 - nx, ny2 - ny)
                merged = True
                break
        if not merged:
            merged_boxes.append((x, y, w, h))

    # Sort by reading order: top-to-bottom, left-to-right
    merged_boxes = sorted(merged_boxes, key=lambda b: (b[1], b[0]))

    extracted_text = []
    for x, y, bw, bh in merged_boxes:
        # Crop with margin
        x1 = max(0, x - 5)
        y1 = max(0, y - 5)
        x2 = min(img_w, x + bw + 5)
        y2 = min(img_h, y + bh + 5)

        crop = gray[y1:y2, x1:x2]

        # OCR with page segmentation mode 6 (uniform block)
        text = pytesseract.image_to_string(crop, config='--psm 6 --oem 3')
        cleaned = text.strip()

        # Only include text blocks with meaningful content
        if len(cleaned) > 20:
            extracted_text.append(cleaned)

    if not extracted_text:
        # Fallback: read entire page with automatic layout analysis
        return pytesseract.image_to_string(gray, config='--psm 1 --oem 3').strip()

    # Join text blocks with proper spacing
    raw_combined = "\n\n".join(extracted_text)

    # Clean up text
    clean_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', raw_combined)  # Fix hyphenation
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)  # Normalize multiple newlines
    clean_text = re.sub(r'[ \t]{2,}', ' ', clean_text)  # Fix multiple spaces/tabs
    clean_text = re.sub(r'\s+$', '', clean_text, flags=re.MULTILINE)  # Remove trailing spaces

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