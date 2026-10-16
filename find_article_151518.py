import sqlite3

conn = sqlite3.connect('archive.db')
c = conn.cursor()

c.execute("""SELECT id FROM articles
             WHERE file_name = ? AND folder_name = ?""",
          ('Document_2026-08-14_151518.jpg', '1992'))

result = c.fetchone()
if result:
    print(f"ID: {result[0]}")
else:
    print("Not found")

conn.close()
