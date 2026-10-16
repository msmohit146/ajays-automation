import sqlite3

conn = sqlite3.connect('archive.db')
c = conn.cursor()

# Test "dalal street" search with new AND logic
print("Testing improved search with AND logic:\n")

# Old way (OR) - any article with "dalal" OR "street"
c.execute("SELECT COUNT(*) FROM articles WHERE LOWER(parsed_text) LIKE ? OR LOWER(parsed_text) LIKE ?",
          ('%dalal%', '%street%'))
old_count = c.fetchone()[0]
print(f'OLD search (OR logic) - "dalal" OR "street": {old_count} results')

# New way (AND) - must have both "dalal" AND "street"
c.execute("SELECT COUNT(*) FROM articles WHERE LOWER(parsed_text) LIKE ? AND LOWER(parsed_text) LIKE ?",
          ('%dalal%', '%street%'))
new_count = c.fetchone()[0]
print(f'NEW search (AND logic) - "dalal" AND "street": {new_count} results')

print("\nSample articles with both words:")
c.execute("""SELECT id, file_name, folder_name
             FROM articles
             WHERE LOWER(parsed_text) LIKE ? AND LOWER(parsed_text) LIKE ?
             LIMIT 5""",
          ('%dalal%', '%street%'))
for row in c.fetchall():
    print(f"  ID {row[0]}: {row[1]} ({row[2]})")

conn.close()
