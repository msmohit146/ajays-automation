import sqlite3

conn = sqlite3.connect('archive.db')
c = conn.cursor()

# Find the article
c.execute("""SELECT id, file_name, folder_name, parsed_text
             FROM articles
             WHERE file_name LIKE '%150859%' AND folder_name = '1992'""")

result = c.fetchone()
if result:
    article_id, file_name, folder_name, text = result
    print(f"Found article to delete:")
    print(f"  ID: {article_id}")
    print(f"  File: {file_name}")
    print(f"  Folder: {folder_name}")
    print(f"  Text preview: {text[:100] if text else 'No text'}...")
    print(f"\nTo delete this article, run: python delete_article.py {article_id}")
else:
    # Try searching by different pattern
    c.execute("""SELECT id, file_name, folder_name
                 FROM articles
                 WHERE folder_name = '1992'
                 ORDER BY id DESC LIMIT 5""")
    print("Article not found. Recent 1992 articles:")
    for row in c.fetchall():
        print(f"  ID {row[0]}: {row[1]}")

conn.close()
