import sqlite3
from collections import defaultdict
import re

def normalize_text(text):
    """Normalize text for comparison."""
    text = (text or "").replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text

db_path = "archive.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all articles
cursor.execute("""
    SELECT id, file_name, folder_name, file_path, parsed_text
    FROM articles
    ORDER BY id
""")
articles = cursor.fetchall()
conn.close()

print(f"Total articles: {len(articles)}")

# Group by normalized text
text_groups = defaultdict(list)
for article_id, file_name, folder_name, file_path, parsed_text in articles:
    key = normalize_text(parsed_text)
    if key:
        text_groups[key].append({
            'id': article_id,
            'file_name': file_name,
            'folder_name': folder_name,
            'file_path': file_path
        })

# Find duplicates (same text but different articles)
duplicate_groups = [group for group in text_groups.values() if len(group) > 1]
total_duplicated_records = sum(len(g) for g in duplicate_groups)

print(f"\nDuplicate groups found: {len(duplicate_groups)}")
print(f"Total records in duplicate groups: {total_duplicated_records}")

# Show first 10 duplicate groups
print("\n=== FIRST 10 DUPLICATE GROUPS ===\n")
for i, group in enumerate(duplicate_groups[:10]):
    print(f"Group {i+1} ({len(group)} copies):")
    for record in group:
        print(f"  ID {record['id']}: {record['file_name']} ({record['folder_name']})")
    print()
