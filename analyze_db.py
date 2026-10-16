import sqlite3
conn = sqlite3.connect('archive.db')
cursor = conn.cursor()

# Check for duplicate file names
cursor.execute('SELECT file_name, COUNT(*) as count FROM articles GROUP BY file_name HAVING count > 1')
duplicates = cursor.fetchall()
print("Duplicate file names:", len(duplicates))
if duplicates:
    for dup in duplicates[:5]:
        print(f"  {dup[0]}: {dup[1]} entries")

# Check total articles
cursor.execute('SELECT COUNT(*) FROM articles')
total = cursor.fetchone()[0]
print(f"\nTotal articles in DB: {total}")

# Check for specific file
print("\nChecking 'Document_2026-09-15_122443.jpg':")
cursor.execute('SELECT id, file_name, file_path, parsed_text FROM articles WHERE file_name = "Document_2026-09-15_122443.jpg"')
rows = cursor.fetchall()
print(f"Found {len(rows)} entry/entries")
for row in rows:
    print(f"  ID: {row[0]}")
    print(f"  File: {row[1]}")
    print(f"  Path: {row[2]}")
    print(f"  Text preview: {row[3][:100]}...")

conn.close()
