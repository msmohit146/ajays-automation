import sqlite3
conn = sqlite3.connect('archive.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(DISTINCT folder_name) FROM articles')
folders = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM articles WHERE parsed_text IS NOT NULL AND length(parsed_text) > 0')
ocr_count = cursor.fetchone()[0]
print(f'Folders/Eras: {folders}')
print(f'Scans with OCR text: {ocr_count}')
conn.close()
