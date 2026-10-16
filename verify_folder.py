import sqlite3
import os
from PIL import Image

def verify_folder(folder_name):
    """Verify OCR text matches images in a folder"""

    if not os.path.exists('archive.db'):
        print("Database not ready yet")
        return False

    conn = sqlite3.connect('archive.db')
    cursor = conn.cursor()

    # Get all articles from this folder
    cursor.execute('SELECT id, file_name, file_path, parsed_text FROM articles WHERE folder_name = ?', (folder_name,))
    articles = cursor.fetchall()

    if not articles:
        print(f"No articles found for folder: {folder_name}")
        return False

    print("\n" + "="*70)
    print(f"VERIFYING FOLDER: {folder_name}")
    print("="*70 + "\n")
    print(f"Total articles in folder: {len(articles)}\n")

    issues = []
    verified = 0

    for id, file_name, file_path, parsed_text in articles:
        print(f"[{id}] {file_name}")

        # Check 1: File exists
        if not os.path.exists(file_path):
            issues.append(f"  [ERROR] FILE NOT FOUND: {file_path}")
            print(f"  [ERROR] FILE NOT FOUND")
            continue

        # Check 2: Image can be loaded
        try:
            img = Image.open(file_path)
            print(f"  [OK] Image found ({img.size[0]}x{img.size[1]})")
        except Exception as e:
            issues.append(f"  [ERROR] CANNOT LOAD IMAGE: {file_name}")
            print(f"  [ERROR] CANNOT LOAD IMAGE")
            continue

        # Check 3: Text is not empty
        if not parsed_text or len(parsed_text.strip()) < 20:
            issues.append(f"  [ERROR] EMPTY/TOO SHORT TEXT: {file_name}")
            print(f"  [ERROR] EMPTY OR TOO SHORT TEXT")
            continue

        # Check 4: Text preview
        text_preview = parsed_text[:80].replace('\n', ' ')
        print(f"  [OK] Text: {text_preview}...")

        # Check 5: Word count validation
        words = len(parsed_text.split())
        if words < 5:
            issues.append(f"  [WARNING] TOO FEW WORDS ({words}): {file_name}")
            print(f"  [WARNING] TOO FEW WORDS ({words})")
            continue

        print(f"  [OK] Words: {words}")
        verified += 1
        print()

    conn.close()

    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    print(f"[OK] Verified: {verified}/{len(articles)}")

    if issues:
        print(f"\n[ERROR] ISSUES FOUND ({len(issues)}):")
        for issue in issues:
            print(issue)
        return False
    else:
        print("\n[OK] ALL ARTICLES VERIFIED - NO ISSUES!")
        return True

if __name__ == "__main__":
    result = verify_folder("2008- Newest @Top")
    if not result:
        print("\n[WARNING] Issues found in 2008 folder. Fix these before continuing.")
        exit(1)
    else:
        print("\n[OK] 2008 folder is GOOD! Safe to continue to next folder.")
        exit(0)
