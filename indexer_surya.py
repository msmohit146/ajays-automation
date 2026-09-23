import os
import re
import sqlite3
import numpy as np
from PIL import Image, ImageOps, ImageEnhance
import traceback
import sys
import shutil

DB_NAME = "archive.db"
ROOT_DIR = "images"

print("Starting Surya advanced document layout analyzer...", flush=True)
sys.stdout.flush()

try:
    print("Loading Surya OCR model...", flush=True)
    sys.stdout.flush()
    from surya.ocr import run_ocr
    from surya.model_registry import get_model

    print("Surya OCR loaded successfully with advanced layout analysis!", flush=True)
    use_surya = True
except Exception as e:
    print(f"ERROR loading Surya: {e}", flush=True)
    print("Falling back to doctr...", flush=True)
    sys.stdout.flush()

    try:
        from doctr.io import DocumentFile
        from doctr.models import ocr_predictor
        model_doctr = ocr_predictor(pretrained=True)
        print("doctr loaded with fallback!", flush=True)
        use_surya = False
    except:
        print("Falling back to EasyOCR...", flush=True)
        import easyocr
        try:
            reader = easyocr.Reader(['en'], gpu=True, verbose=False)
            print("EasyOCR loaded with GPU!", flush=True)
        except:
            reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            print("EasyOCR loaded with CPU!", flush=True)
        use_surya = False

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

def extract_text_surya(image_path):
    """Extract text using Surya with layout analysis"""
    try:
        from surya.ocr import run_ocr

        # Surya performs OCR with document layout understanding
        predictions = run_ocr([image_path], languages=['en'], det_model_name='en_detector')

        if not predictions or len(predictions) == 0:
            return ""

        # Extract text preserving layout from first image
        pred = predictions[0]

        texts = []
        for text_block in pred.text_lines:
            if text_block.text.strip():
                texts.append(text_block.text.strip())

        if not texts:
            return ""

        text = '\n'.join(texts)
        return text
    except Exception as e:
        print(f"ERROR in Surya for {image_path}: {e}", flush=True)
        return ""

def extract_text_doctr(image_path):
    """Fallback doctr extraction"""
    try:
        from doctr.io import DocumentFile

        doc = DocumentFile.from_image(image_path)
        result = model_doctr(doc)

        texts = []
        for page in result.pages:
            for block in page.blocks:
                block_text = []
                for line in block.lines:
                    line_text = []
                    for word in line.words:
                        if word.confidence > 0.2:
                            line_text.append(word.value)
                    if line_text:
                        block_text.append(' '.join(line_text))

                if block_text:
                    texts.append('\n'.join(block_text))

        if not texts:
            return ""

        text = '\n\n'.join(texts)
        return text
    except Exception as e:
        print(f"ERROR in doctr for {image_path}: {e}", flush=True)
        return ""

def extract_text_easyocr(image_path, reader):
    """Fallback EasyOCR extraction"""
    try:
        img = preprocess_image(image_path)
        if img is None:
            return ""

        img_array = np.array(img)

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

            if confidence < 0.15:
                continue

            y_pos = bbox[0][1]

            if last_y is not None and abs(y_pos - last_y) > 12:
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

    print(f"Processing {len(images_to_process)} remaining files with Surya...", flush=True)
    sys.stdout.flush()

    # Process images
    for idx, (full_path, file, folder) in enumerate(images_to_process):
        print(f"Progress: {processed_count + idx + 1}/{total_images} - {file}", flush=True)
        sys.stdout.flush()

        try:
            if use_surya:
                text = extract_text_surya(full_path)
            else:
                text = extract_text_doctr(full_path)
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

    print(f"COMPLETE! All {total_images} files indexed with Surya layout analysis.", flush=True)
    sys.stdout.flush()

except Exception as e:
    print(f"FATAL ERROR: {e}", flush=True)
    traceback.print_exc()
    sys.stdout.flush()
    sys.exit(1)
