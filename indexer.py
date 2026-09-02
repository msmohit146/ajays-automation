import os
import re
import time
import sqlite3
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

def find_best_rotation_angle(img):
    """Detects best rotation angle using OSD with a 4-angle word score fallback."""
    # Method 1: Try Tesseract OSD
    try:
        osd = pytesseract.image_to_osd(img)
        angle = int(re.search(r'Rotate: (\d+)', osd).group(1))
        conf = float(re.search(r'Orientation confidence: ([\d\.]+)', osd).group(1))
        if conf > 1.5:
            return angle
    except Exception:
        pass

    # Method 2: Test 0°, 90°, 180°, and 270° on a lightweight thumbnail
    thumb = img.copy()
    thumb.thumbnail((600, 600))
    
    best_angle = 0
    max_word_count = -1

    for angle in [0, 90, 180, 270]:
        test_img = thumb.rotate(360 - angle, expand=True) if angle != 0 else thumb
        data = pytesseract.image_to_data(test_img, output_type=pytesseract.Output.DICT)
        
        # Count words recognized with >40% confidence
        word_count = sum(1 for t, c in zip(data['text'], data['conf']) if int(c) > 40 and len(t.strip()) > 2)
        
        if word_count > max_word_count:
            max_word_count = word_count
            best_angle = angle

    return best_angle

def process_and_fix_image(image_path):
    img = Image.open(image_path)
    
    angle = find_best_rotation_angle(img)
    if angle in (90, 180, 270):
        img = img.rotate(360 - angle, expand=True)
        try:
            img.save(image_path)  # Overwrite image upright for Streamlit display
        except Exception:
            pass

    # Extract text on the upright image using column mode (--psm 1)
    raw_text = pytesseract.image_to_string(img, config=r'--psm 1 --oem 3')
    
    # Clean up hyphenated column breaks
    cleaned_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', raw_text)
    return cleaned_text

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