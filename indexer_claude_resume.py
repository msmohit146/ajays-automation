import os
import re
import sqlite3
import numpy as np
from PIL import Image, ImageOps, ImageEnhance
import easyocr
import cv2
import traceback
import sys
import asyncio
from anthropic import AsyncAnthropic
from concurrent.futures import ThreadPoolExecutor
import shutil

DB_NAME = "archive.db"
ROOT_DIR = "images"
PARALLEL_WORKERS = 6

print("Starting parallel Claude API indexer with RESUME support...", flush=True)
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

def extract_text_from_region(img_array):
    """Extract text from image region using EasyOCR"""
    try:
        if len(img_array.shape) == 2:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
        elif img_array.shape[2] == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)

        results = reader.readtext(img_array, detail=1)
        if not results:
            return ""

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

def preprocess_image(image_path):
    """Preprocess image for better OCR accuracy"""
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)
        return img
    except:
        return None

def extract_raw_ocr(image_path):
    """Extract raw OCR text from image (blocking operation)"""
    try:
        img = preprocess_image(image_path)
        if img is None:
            return ""
        img_array = np.array(img)
        if img_array.size == 0:
            return ""
        return extract_text_from_region(img_array)
    except:
        return ""

async def parse_with_claude(raw_ocr_text, client):
    """Parse and restructure OCR text using Claude API (async)"""
    if not raw_ocr_text.strip():
        return ""

    try:
        response = await client.messages.create(
            model="claude-opus-5",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": f"""You are an OCR text parser. I have extracted text from a newspaper/document scan using OCR.
The text may have:
- Mixed columns (text from left and right columns jumbled together)
- OCR errors and typos
- Inconsistent spacing and formatting

Please:
1. Identify and fix OCR errors
2. Reorganize multi-column text into proper reading order (left column first, then right column)
3. Preserve article structure, headers, and body text
4. Clean up spacing and formatting
5. Return only the cleaned, properly-ordered text

Raw OCR text:
{raw_ocr_text}

Return the cleaned text only, no explanations or metadata."""
                }
            ]
        )

        cleaned_text = response.content[0].text.strip()
        return cleaned_text
    except Exception as e:
        print(f"ERROR parsing with Claude: {e}", flush=True)
        return raw_ocr_text

async def process_image_async(image_path, file, folder, idx, total, client, executor):
    """Process single image with async Claude API call"""
    try:
        print(f"Progress: {idx+1}/{total} - {file}", flush=True)
        sys.stdout.flush()

        loop = asyncio.get_event_loop()
        raw_text = await loop.run_in_executor(executor, extract_raw_ocr, image_path)

        if not raw_text.strip():
            return (file, folder, image_path.replace("\\", "/"), "")

        cleaned_text = await parse_with_claude(raw_text, client)

        if not cleaned_text.strip():
            return (file, folder, image_path.replace("\\", "/"), "")

        final_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', cleaned_text)
        final_text = re.sub(r'\n{3,}', '\n\n', final_text)
        final_text = re.sub(r'[ \t]{2,}', ' ', final_text)
        final_text = re.sub(r'\s+$', '', final_text, flags=re.MULTILINE)

        return (file, folder, image_path.replace("\\", "/"), final_text.strip())
    except Exception as e:
        print(f"ERROR processing {file}: {e}", flush=True)
        return (file, folder, image_path.replace("\\", "/"), "")

async def main():
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

        if os.path.exists(DB_NAME):
            print("RESUME MODE: Found existing database, skipping already processed files...", flush=True)
            sys.stdout.flush()
            shutil.copy(DB_NAME, temp_db)

            conn = sqlite3.connect(temp_db, timeout=30)
            cursor = conn.cursor()
            cursor.execute("SELECT file_name FROM articles")
            processed_files = set(row[0] for row in cursor.fetchall())
            conn.close()

            print(f"Skipping {len(processed_files)} already processed files", flush=True)
            sys.stdout.flush()
        else:
            # Create new database
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

        # Filter to only unprocessed images
        images_to_process = [(p, f, fol) for p, f, fol in image_list if f not in processed_files]
        processed_count = len(processed_files)

        print(f"Processing {len(images_to_process)} remaining files...", flush=True)
        sys.stdout.flush()

        # Initialize async client
        client = AsyncAnthropic()
        executor = ThreadPoolExecutor(max_workers=PARALLEL_WORKERS)

        # Process in batches
        for i in range(0, len(images_to_process), PARALLEL_WORKERS):
            batch = images_to_process[i:i+PARALLEL_WORKERS]

            tasks = [
                process_image_async(full_path, file, folder, processed_count + i + j, total_images, client, executor)
                for j, (full_path, file, folder) in enumerate(batch)
            ]

            results = await asyncio.gather(*tasks)

            # Insert into database
            for file, folder, path, text in results:
                conn = sqlite3.connect(temp_db, timeout=30)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO articles (file_name, folder_name, file_path, parsed_text)
                    VALUES (?, ?, ?, ?)
                ''', (file, folder, path, text))
                conn.commit()
                conn.close()

        executor.shutdown(wait=True)

        # Replace old database
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
        shutil.move(temp_db, DB_NAME)

        print(f"COMPLETE! All {total_images} files indexed with parallel Claude API.", flush=True)
        sys.stdout.flush()

    except Exception as e:
        print(f"FATAL ERROR: {e}", flush=True)
        traceback.print_exc()
        sys.stdout.flush()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
