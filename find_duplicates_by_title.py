import sqlite3
import re
from collections import defaultdict

def extract_title(text):
    """Extract the first line (likely the article title)."""
    if not text:
        return None
    lines = text.strip().split('\n')
    # Get first non-empty line as title
    for line in lines:
        clean = line.strip()
        if clean and len(clean) > 5:  # Must be meaningful
            return clean.casefold()
    return None

db_path = "archive.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all articles
cursor.execute("""
    SELECT id, file_name, folder_name, file_path, parsed_text
    FROM articles
    ORDER BY file_name
""")
articles = cursor.fetchall()
conn.close()

print(f"Total articles: {len(articles)}\n")

# Group by title
title_groups = defaultdict(list)
for article_id, file_name, folder_name, file_path, parsed_text in articles:
    title = extract_title(parsed_text)
    if title:
        title_groups[title].append({
            'id': article_id,
            'file_name': file_name,
            'folder_name': folder_name,
            'file_path': file_path,
            'title': title
        })

# Find groups with multiple articles (potential duplicates)
duplicate_groups = [group for group in title_groups.values() if len(group) > 1]

print(f"Articles with same title: {len(duplicate_groups)} groups")
print(f"Total duplicate articles: {sum(len(g) for g in duplicate_groups)}\n")

# Show all duplicate groups
for i, group in enumerate(duplicate_groups[:30]):
    print(f"Group {i+1}: {group[0]['title'][:80]}")
    for record in group:
        print(f"  ID {record['id']:4d} | {record['file_name']:50s} | {record['folder_name']}")
    print()
