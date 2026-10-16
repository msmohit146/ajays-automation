import sqlite3
from collections import defaultdict
from difflib import SequenceMatcher
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

# Find near-duplicates by comparing all pairs
near_duplicates = []
for i, article1 in enumerate(articles):
    id1, file_name1, folder_name1, file_path1, text1 = article1
    norm_text1 = normalize_text(text1)

    for article2 in articles[i+1:]:
        id2, file_name2, folder_name2, file_path2, text2 = article2
        norm_text2 = normalize_text(text2)

        # Skip if texts are empty
        if not norm_text1 or not norm_text2:
            continue

        # Calculate similarity
        similarity = SequenceMatcher(None, norm_text1, norm_text2).ratio()

        # Keep high-similarity pairs (>=85%)
        if similarity >= 0.85:
            near_duplicates.append((
                similarity,
                id1, file_name1, folder_name1,
                id2, file_name2, folder_name2
            ))

# Sort by similarity (highest first)
near_duplicates.sort(reverse=True)

print(f"\nNear-duplicates found (>=85% similar): {len(near_duplicates)}\n")

# Show first 20
for i, (similarity, id1, fn1, fld1, id2, fn2, fld2) in enumerate(near_duplicates[:20]):
    print(f"{i+1}. Similarity: {similarity*100:.1f}%")
    print(f"   ID {id1}: {fn1} ({fld1})")
    print(f"   ID {id2}: {fn2} ({fld2})")
    print()
