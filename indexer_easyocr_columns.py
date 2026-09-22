import os
import re
import sqlite3
import numpy as np
from PIL import Image, ImageOps, ImageEnhance
import easyocr
import cv2
import traceback
import sys

DB_NAME = "archive.db"
ROOT_DIR = "images"

print("Starting EasyOCR with improved column detection...", flush=True)
sys.stdout.flush()

try:
    print("Loading EasyOCR...", flush=True)
    sys.stdout.flush()
    reader = easyocr.Reader(['en'], gpu=True, verbose=False)
    print("EasyOCR loaded with GPU!", flush=True)
except:
    print("GPU not available, using CPU...", flush=True)
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    print("EasyOCR loaded with CPU!", flush=True)

sys.stdout.flush()

def detect_columns_improved(image):
    """Improved column detection using morphological operations"""
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply Otsu's thresholding
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Close small gaps in text
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 10))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # Dilate to connect nearby text
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 20))
        dilated = cv2.dilate(closed, kernel, iterations=3)

        # Get vertical projection (sum of black pixels in each column)
        vertical_projection = np.sum(dilated == 0, axis=0)

        # Normalize projection
        max_proj = np.max(vertical_projection)
        if max_proj == 0:
            return None

        vertical_projection = vertical_projection / max_proj

        # Find gaps in text (white space columns)
        gap_threshold = 0.15
        gaps = vertical_projection < gap_threshold

        # Find column boundaries
        boundaries = []
        in_gap = gaps[0]
        for i in range(1, len(gaps)):
            if gaps[i] != in_gap:
                boundaries.append(i)
                in_gap = gaps[i]

        # Extract column regions
        columns = []
        min_col_width = image.shape[1] * 0.15  # Minimum 15% of image width

        i = 0
        while i < len(boundaries) - 1:
            col_start = boundaries[i]
            col_end = boundaries[i + 1]
            col_width = col_end - col_start

            if col_width > min_col_width:
                columns.append((col_start, col_end))
                i += 2
            else:
                i += 1

        if len(columns) >= 2:
            return columns

        return None
    except:
        return None

def preprocess_image(image_path):
    """Preprocess image for better OCR accuracy"""
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)

        # Enhance brightness
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)

        return img
    except:
        return None

def extract_text_from_region(img_array, reader):
    """Extract text from image region"""
    try:
        if len(img_array.shape) == 2:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
        elif img_array.shape[2] == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)

        results = reader.readtext(img_array, detail=1)
        if not results:
            return ""

        # Sort by Y position (top to bottom), then X (left to right)
        sorted_results = sorted(results, key=lambda r: (r[0][0][1], r[0][0][0]))

        lines = []
        current_line = []
        last_y = None

        for detection in sorted_results:
            bbox = detection[0]
            text = detection[1]
            confidence = detection[2]

            if confidence < 0.2:
                continue

            y_pos = bbox[0][1]

            # New line detection
            if last_y is not None and abs(y_pos - last_y) > 15:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = []

            current_line.append(text)
            last_y = y_pos

        if current_line:
            lines.append(' '.join(current_line))

        return '\n'.join(lines)
    except:
        return ""

def extract_text_ocr(image_path):
    """Extract text with improved column handling"""
    try:
        img = preprocess_image(image_path)
        if img is None:
            return ""

        img_array = np.array(img)
    except:
        return ""

    if img_array.size == 0:
        return ""

    # Try to detect columns
    if len(img_array.shape) == 3 and img_array.shape[2] in [3, 4]:
        if img_array.shape[2] == 4:
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        else:
            img_bgr = img_array

        columns = detect_columns_improved(img_bgr)

        if columns and len(columns) >= 2:
            # Process each column separately, left to right
            all_text = []
            for col_start, col_end in columns:
                col_region = img_array[:, col_start:col_end]
                col_text = extract_text_from_region(col_region, reader)
                if col_text.strip():
                    all_text.append(col_text)

            if all_text:
                text = '\n\n'.join(all_text)
            else:
                # Fallback to single region if column processing failed
                text = extract_text_from_region(img_array, reader)
        else:
            # No columns detected, process as single region
            text = extract_text_from_region(img_array, reader)
    else:
        text = extract_text_from_region(img_array, reader)

    if not text.strip():
        return ""

    # Clean up text
    clean_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
    clean_text = re.sub(r'[ \t]{2,}', ' ', clean_text)
    clean_text = re.sub(r'\s+$', '', clean_text, flags=re.MULTILINE)

    return clean_text.strip()

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

    # Create temp database
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

    # Process all images
    for idx, (full_path, file, folder) in enumerate(image_list):
        print(f"Progress: {idx+1}/{total_images} - {file}", flush=True)
        sys.stdout.flush()

        try:
            text = extract_text_ocr(full_path)
        except Exception as e:
            print(f"ERROR processing {file}: {e}", flush=True)
            text = ""

        path = full_path.replace("\\", "/")

        conn = sqlite3.connect(temp_db, timeout=30)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO articles (file_name, folder_name, file_path, parsed_text)
            VALUES (?, ?, ?, ?)
        ''', (file, folder, path, text))
        conn.commit()
        conn.close()

    # Replace old database with new one
    import shutil
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    shutil.move(temp_db, DB_NAME)

    print(f"COMPLETE! {total_images} files indexed with improved column detection.", flush=True)
    sys.stdout.flush()

except Exception as e:
    print(f"FATAL ERROR: {e}", flush=True)
    traceback.print_exc()
    sys.stdout.flush()
    sys.exit(1)
