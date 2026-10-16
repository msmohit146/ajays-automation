import sqlite3

conn = sqlite3.connect('archive.db')
c = conn.cursor()

# Find articles to delete
articles_to_find = [
    ('2026-08-14_150859.jpg', '1992'),  # Already found: ID 201
    ('Document_2026-08-14_145739.jpg', '1992'),
]

deletion_list = []

for filename, folder in articles_to_find:
    c.execute("""SELECT id, file_name, folder_name
                 FROM articles
                 WHERE file_name = ? AND folder_name = ?""",
              (filename, folder))
    result = c.fetchone()
    if result:
        article_id = result[0]
        deletion_list.append(article_id)
        print(f"✓ Found: ID {article_id} - {filename}")
    else:
        print(f"✗ Not found: {filename}")

print(f"\nArticles to delete: {deletion_list}")
print(f"Total: {len(deletion_list)}")

conn.close()
