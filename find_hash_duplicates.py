import sqlite3
import re
from collections import defaultdict
from difflib import SequenceMatcher

def get_text_hash(text):
    """Get first 500 chars normalized - quick way to find candidates."""
    text = (text or "").lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:500]

db_path = "archive.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, file_name, folder_name, parsed_text FROM articles ORDER BY id")
articles = cursor.fetchall()
conn.close()

print(f"Total articles: {len(articles)}")

# Hash-based grouping for potential duplicates
hash_groups = defaultdict(list)
for article_id, file_name, folder_name, parsed_text in articles:
    hash_key = get_text_hash(parsed_text)
    if hash_key:
        hash_groups[hash_key].append((article_id, file_name, folder_name, parsed_text))

# Find groups with potential duplicates
duplicates = []
for hash_key, group in hash_groups.items():
    if len(group) > 1:
        # These have identical first 500 chars - definitely duplicates
        duplicates.extend(group)
        print(f"Found {len(group)} articles with identical text start:")
        for aid, fn, fold, txt in group:
            print(f"  ID {aid}: {fn} ({fold}) - {len(txt or '')} chars")

print(f"\nTotal articles with identical text starts: {len(duplicates)}")
