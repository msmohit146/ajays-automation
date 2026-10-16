import sqlite3

conn = sqlite3.connect('archive.db')
c = conn.cursor()

c.execute("""SELECT id, file_name, parsed_text FROM articles
             WHERE file_name = ? AND folder_name = ?""",
          ('Document_2026-08-14_150500.jpg', '1992'))

result = c.fetchone()
if result:
    article_id, file_name, text = result
    print(f"ID: {article_id}")
    print(f"File: {file_name}")
    print(f"\nCurrent text (first 500 chars):")
    print(text[:500] if text else "No text")
    print(f"\nTotal length: {len(text) if text else 0} chars")
else:
    print("Not found")

conn.close()
