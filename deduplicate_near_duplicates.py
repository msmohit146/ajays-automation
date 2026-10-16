import sqlite3
import re
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime
import json

def normalize_text(text):
    """Normalize text for comparison - remove punctuation and extra whitespace."""
    text = (text or "").lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def score_article(article):
    """Score articles - prefer original file names, longer text, etc."""
    article_id, file_name, folder_name, file_path, parsed_text = article
    score = 0

    # Prefer files with actual content over "Document_*" names
    if not file_name.startswith("Document_"):
        score += 100

    # Prefer files from original folders (lower year numbers)
    try:
        year_str = folder_name.split()[0]
        year = int(year_str)
        score += (2030 - year)
    except (ValueError, IndexError):
        score += 1000

    # Prefer longer OCR text (more complete)
    text_len = len(parsed_text or "")
    score += min(text_len // 100, 50)

    return score, article

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("""
    SELECT id, file_name, folder_name, file_path, parsed_text
    FROM articles
    ORDER BY id
""")
articles = cursor.fetchall()
conn.close()

print(f"Total articles: {len(articles)}")

# Find near-duplicates with high text similarity
near_duplicates = []
checked_pairs = set()

for i, article1 in enumerate(articles):
    id1, fn1, fld1, fp1, txt1 = article1
    norm1 = normalize_text(txt1)

    if not norm1 or len(norm1) < 100:  # Skip very short texts
        continue

    for article2 in articles[i+1:]:
        id2, fn2, fld2, fp2, txt2 = article2
        norm2 = normalize_text(txt2)

        if not norm2 or len(norm2) < 100:
            continue

        # Calculate similarity
        similarity = SequenceMatcher(None, norm1, norm2).ratio()

        # Keep high-similarity pairs (>=80% - more aggressive)
        if similarity >= 0.80:
            near_duplicates.append({
                'similarity': similarity,
                'article1': article1,
                'article2': article2,
            })

near_duplicates.sort(key=lambda x: x['similarity'], reverse=True)

print(f"\nNear-duplicates found (>=80% similar): {len(near_duplicates)}")

# Group near-duplicates to avoid removing both from the same group
ids_to_remove = set()
removal_report = []

for item in near_duplicates:
    similarity = item['similarity']
    article1 = item['article1']
    article2 = item['article2']

    id1, fn1, fld1, fp1, txt1 = article1
    id2, fn2, fld2, fp2, txt2 = article2

    # Skip if either has already been marked for removal
    if id1 in ids_to_remove or id2 in ids_to_remove:
        continue

    # Score and keep the better one
    score1, _ = score_article(article1)
    score2, _ = score_article(article2)

    if score1 >= score2:
        ids_to_remove.add(id2)
        removal_report.append({
            'similarity': similarity,
            'kept_id': id1,
            'kept_file': fn1,
            'removed_id': id2,
            'removed_file': fn2,
        })
    else:
        ids_to_remove.add(id1)
        removal_report.append({
            'similarity': similarity,
            'kept_id': id2,
            'kept_file': fn2,
            'removed_id': id1,
            'removed_file': fn1,
        })

print(f"IDs marked for removal: {len(ids_to_remove)}")

if ids_to_remove:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    placeholders = ",".join("?" * len(ids_to_remove))
    cursor.execute(f"DELETE FROM articles WHERE id IN ({placeholders})", list(ids_to_remove))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM articles")
    final_count = cursor.fetchone()[0]
    conn.close()

    print(f"\nRemoved {len(ids_to_remove)} near-duplicate articles")
    print(f"Final article count: {final_count}")

    # Save detailed report
    report = {
        'timestamp': datetime.now().isoformat(),
        'near_duplicates_removed': len(ids_to_remove),
        'final_count': final_count,
        'removals': removal_report[:20]  # Show first 20
    }

    with open("near_dedup_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\nTop near-duplicates removed:")
    for item in removal_report[:10]:
        print(f"  {item['similarity']*100:.1f}% similar: kept ID {item['kept_id']} ({item['kept_file']}), removed ID {item['removed_id']} ({item['removed_file']})")
else:
    print("No near-duplicates to remove")
