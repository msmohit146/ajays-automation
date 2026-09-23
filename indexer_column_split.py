import os
import re
import sqlite3
import numpy as np
import cv2
from PIL import Image, ImageOps, ImageEnhance
import traceback
import sys
import shutil
import easyocr

DB_NAME = "archive.db"
ROOT_DIR = "images"

print("Starting column-splitting OCR indexer...", flush=True)
sys.stdout.flush()

try:
    reader = easyocr.Reader(['en'], gpu=True, verbose=False)
    print("EasyOCR loaded with GPU!", flush=True)
except:
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    print("EasyOCR loaded with CPU!", flush=True)

sys.stdout.flush()

def preprocess_image(image_path):
    """Preprocess image"""
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)

        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.8)

        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.15)

        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.2)

        return img
    except:
        return None

def detect_columns(image_array):
    """Detect column boundaries using vertical projection"""
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)

    # Threshold to get binary image
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    # Calculate vertical projection (sum of white pixels in each column)
    vertical_projection = np.sum(binary, axis=0)

    # Find columns (gaps between text)
    height = image_array.shape[0]
    threshold = height * 0.3  # 30% of height

    column_gaps = []
    in_gap = False
    gap_start = 0

    for i, val in enumerate(vertical_projection):
        if val < threshold:
            if not in_gap:
                gap_start = i
                in_gap = True
        else:
            if in_gap and i - gap_start > 20:  # Gap must be at least 20 pixels wide
                column_gaps.append((gap_start, i))
            in_gap = False

    return column_gaps

def extract_text_from_columns(image_path):
    """Extract text by splitting into columns first"""
    try:
        img = preprocess_image(image_path)
        if img is None:
            return ""

        img_array = np.array(img)

        # Detect column boundaries
        gaps = detect_columns(img_array)

        if len(gaps) < 1:
            # No clear columns detected, do regular OCR
            results = reader.readtext(img_array, detail=1)
            if not results:
                return ""

            sorted_results = sorted(results, key=lambda r: (r[0][0][1], r[0][0][0]))
            texts = [r[1] for r in sorted_results if r[2] > 0.15]
            return '\n'.join(texts)

        # Split into columns and extract text from each
        width = img_array.shape[1]
        column_texts = []

        # Define column regions
        column_regions = []
        prev_end = 0

        for gap_start, gap_end in gaps:
            if gap_start > prev_end + 10:
                column_regions.append((prev_end, gap_start))
            prev_end = gap_end

        # Add last column
        if prev_end < width - 10:
            column_regions.append((prev_end, width))

        # Extract text from each column
        for col_idx, (col_start, col_end) in enumerate(column_regions):
            col_img = img_array[:, col_start:col_end, :]

            # OCR this column
            results = reader.readtext(col_img, detail=1)

            if results:
                # Sort by Y position (top to bottom) within column
                sorted_results = sorted(results, key=lambda r: r[0][0][1])
                col_text = []

                for detection in sorted_results:
                    text = detection[1]
                    confidence = detection[2]

                    if confidence > 0.15 and text.strip():
                        col_text.append(text.strip())

                if col_text:
                    column_texts.append('\n'.join(col_text))

        # Join columns with paragraph breaks
        if column_texts:
            return '\n\n'.join(column_texts)

        return ""
    except Exception as e:
        print(f"ERROR in column extraction for {image_path}: {e}", flush=True)
        return ""

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

    # Check for existing database (RESUME MODE)
    temp_db = "archive_temp.db"
    processed_files = set()
    processed_count = 0

    if os.path.exists(DB_NAME):
        print("RESUME MODE: Found existing database...", flush=True)
        sys.stdout.flush()
        shutil.copy(DB_NAME, temp_db)

        conn = sqlite3.connect(temp_db, timeout=30)
        cursor = conn.cursor()
        cursor.execute("SELECT file_name FROM articles")
        processed_files = set(row[0] for row in cursor.fetchall())
        processed_count = len(processed_files)
        conn.close()

        print(f"Skipping {processed_count} already processed files", flush=True)
        sys.stdout.flush()
    else:
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

    # Filter unprocessed images
    images_to_process = [(p, f, fol) for p, f, fol in image_list if f not in processed_files]

    print(f"Processing {len(images_to_process)} remaining files with column splitting...", flush=True)
    sys.stdout.flush()

    # Process images
    for idx, (full_path, file, folder) in enumerate(images_to_process):
        print(f"Progress: {processed_count + idx + 1}/{total_images} - {file}", flush=True)
        sys.stdout.flush()

        try:
            text = extract_text_from_columns(full_path)
        except Exception as e:
            print(f"ERROR processing {file}: {e}", flush=True)
            text = ""

        # Clean text
        if text.strip():
            text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[ \t]{2,}', ' ', text)
            text = re.sub(r'\s+$', '', text, flags=re.MULTILINE)
            text = text.strip()

        path = full_path.replace("\\", "/")

        conn = sqlite3.connect(temp_db, timeout=30)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO articles (file_name, folder_name, file_path, parsed_text)
            VALUES (?, ?, ?, ?)
        ''', (file, folder, path, text))
        conn.commit()
        conn.close()

    # Replace database
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    shutil.move(temp_db, DB_NAME)

    print(f"COMPLETE! All {total_images} files indexed with column splitting.", flush=True)
    sys.stdout.flush()

except Exception as e:
    print(f"FATAL ERROR: {e}", flush=True)
    traceback.print_exc()
    sys.stdout.flush()
    sys.exit(1)
