import os
import re
import time
import sqlite3
import cv2
import numpy as np
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

DB_NAME = "archive.db"
IMAGE_FOLDER = r"C:\Users\AB COM\Pictures\ajays"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            file_path TEXT PRIMARY KEY,
            file_name TEXT,
            folder_name TEXT,
            parsed_text TEXT
        )
    ''')
    conn.commit()
    conn.close()

def preprocess_for_ocr(pil_img):
    """Converts image to high-contrast black-and-white to remove background yellowing and noise."""
    # Convert PIL Image to OpenCV numpy array
    img_array = np.array(pil_img.convert('RGB'))
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

    # Upscale 2x if the image/text resolution is low
    h, w = gray.shape
    if h < 1200 or w < 1200:
        gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    # Apply Otsu's thresholding to strip yellowed paper background & ink bleed
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return Image.fromarray(binary)

def clean_ocr_text(text):
    """Removes random floating gibberish symbols while keeping financial terms and standard prose."""
    # Remove random solitary non-alphanumeric noise symbols
    text = re.sub(r'(?<=\s)[^\w\s%.,\-\(\)\$₹£](?=\s)', '', text)
    # Fix hyphenated words broken across lines
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    # Collapse multiple blank lines into standard paragraphs
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def process_and_fix_image(image_path):
    img = Image.open(image_path)

    # 1. Preprocess to high-contrast black & white
    clean_img = preprocess_for_ocr(img)

    # 2. Run OCR with PSM 4 (Column aware for news clips)
    custom_config = r'--psm 4 --oem 3'
    raw_text = pytesseract.image_to_string(clean_img, config=custom_config)

    # 3. Post-process clean text
    return clean_ocr_text(raw_text)

def run_indexer():
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT file_path FROM articles")
    existing_files = set(row[0] for row in cursor.fetchall())
    
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.bmp')
    new_count = 0
    
    for root, dirs, files in os.walk(IMAGE_FOLDER):
        for file in files:
            if file.lower().endswith(valid_extensions):
                file_path = os.path.join(root, file)
                
                if file_path in existing_files:
                    continue
                
                print(f"Scanning & auto-orienting: {file_path}")
                folder_name = os.path.basename(root)
                try:
                    text = process_and_fix_image(file_path)
                    
                    cursor.execute(
                        "INSERT INTO articles (file_path, file_name, folder_name, parsed_text) VALUES (?, ?, ?, ?)",
                        (file_path, file, folder_name, text)
                    )
                    new_count += 1
                    conn.commit()
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                
                time.sleep(0.01)
                    
    conn.close()
    print(f"\nIndexing complete! {new_count} file(s) updated in database.")

if __name__ == "__main__":
    run_indexer()