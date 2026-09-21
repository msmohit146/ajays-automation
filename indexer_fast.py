import os
import re
import sqlite3
import numpy as np
from PIL import Image, ImageOps, ImageEnhance
import easyocr
import cv2
import traceback
import sys
from multiprocessing import Pool, cpu_count
from functools import partial

DB_NAME = "archive.db"
ROOT_DIR = "images"

print(f"Starting fast indexer with {cpu_count()} CPU cores...", flush=True)
sys.stdout.flush()

try:
    print("Loading EasyOCR reader (GPU enabled)...", flush=True)
    sys.stdout.flush()
    reader = easyocr.Reader(['en'], gpu=True, verbose=False)
    print("EasyOCR loaded with GPU!", flush=True)
except:
    print("GPU not available, using CPU...", flush=True)
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    print("EasyOCR loaded with CPU!", flush=True)

sys.stdout.flush()

def preprocess_image_fast(image_path):
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        # Quick contrast boost only
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        return img
    except:
        return None

def extract_text_ocr_fast(image_path):
    try:
        img = preprocess_image_fast(image_path)
        if img is None:
            return ""
        img_array = np.array(img)
    except:
        return ""

    if img_array.size == 0:
        return ""

    try:
        if len(img_array.shape) == 2:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
        elif img_array.shape[2] == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
    except:
        return ""

    try:
        results = reader.readtext(img_array, detail=1)
    except:
        return ""

    if not results:
        return ""

    sorted_results = sorted(results, key=lambda r: (r[0][0][1], r[0][0][0]))
    lines = []
    current_line = []
    last_y = None

    for detection in sorted_results:
        try:
            bbox = detection[0]
            text = detection[1]
            confidence = detection[2]

            if confidence < 0.2:
                continue

            y_pos = bbox[0][1]

            if last_y is not None and abs(y_pos - last_y) > 15:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = []

            current_line.append(text)
            last_y = y_pos
        except:
            continue

    if current_line:
        lines.append(' '.join(current_line))

    text = '\n'.join(lines)

    if not text.strip():
        return ""

    clean_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
    clean_text = re.sub(r'[ \t]{2,}', ' ', clean_text)
    clean_text = re.sub(r'\s+$', '', clean_text, flags=re.MULTILINE)

    return clean_text.strip()

def process_image(image_info):
    full_path, file, folder_name = image_info
    try:
        text = extract_text_ocr_fast(full_path)
        return (file, folder_name, full_path.replace("\\", "/"), text)
    except:
        return (file, folder_name, full_path.replace("\\", "/"), "")

try:
    print("Scanning images...", flush=True)
    sys.stdout.flush()

    image_list = []
    for root, dirs, files in os.walk(ROOT_DIR):
        folder_name = os.path.basename(root)
        if folder_name == ROOT_DIR:
            folder_name = "Root"

        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                full_path = os.path.join(root, file)
                image_list.append((full_path, file, folder_name))

    total_images = len(image_list)
    print(f"Found {total_images} images to process", flush=True)
    sys.stdout.flush()

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
    conn.close()

    count = 0
    for idx, (file, folder, path, text) in enumerate(map(process_image, image_list)):
        if idx % 1 == 0:
            print(f"Progress: {idx+1}/{total_images} - {file}", flush=True)
            sys.stdout.flush()

        conn = sqlite3.connect(temp_db, timeout=30)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO articles (file_name, folder_name, file_path, parsed_text)
            VALUES (?, ?, ?, ?)
        ''', (file, folder, path, text))
        conn.commit()
        conn.close()
        count += 1

    import shutil
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    shutil.move(temp_db, DB_NAME)
    print(f"COMPLETE! {count} files indexed.", flush=True)
    sys.stdout.flush()

except Exception as e:
    print(f"FATAL ERROR: {e}", flush=True)
    traceback.print_exc()
    sys.stdout.flush()
    sys.exit(1)
