import sqlite3
import re
from difflib import SequenceMatcher
from pathlib import Path
import json
from datetime import datetime

def normalize_for_similarity(text):
    """Normalize for similarity comparison."""
    text = (text or "").lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()
    return text

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, file_name, folder_name, file_path, parsed_text FROM articles ORDER BY id")
articles = cursor.fetchall()
conn.close()

print(f"Total articles: {len(articles)}")

# Group by file size to find potential duplicates more efficiently
# Articles with very similar text will have similar byte counts
from collections import defaultdict
size_groups = defaultdict(list)

for article in articles:
    article_id, file_name, folder_name, file_path, parsed_text = article
    text_size = len(parsed_text or "")
    # Group by size buckets (within 1000 chars)
    bucket = (text_size // 1000) * 1000
    size_groups[bucket].append(article)

print(f"Articles grouped into {len(size_groups)} size buckets")

# Now find near-duplicates within size-similar groups
ids_to_remove = set()
removal_report = []

for bucket, group in size_groups.items():
    if len(group) < 2:
        continue

    # Compare articles in this size bucket
    for i, article1 in enumerate(group):
        id1, fn1, fld1, fp1, txt1 = article1

        if id1 in ids_to_remove:
            continue

        norm1 = normalize_for_similarity(txt1)
        if not norm1 or len(norm1) < 50:
            continue

        for article2 in group[i+1:]:
            id2, fn2, fld2, fp2, txt2 = article2

            if id2 in ids_to_remove:
                continue

            norm2 = normalize_for_similarity(txt2)
            if not norm2 or len(norm2) < 50:
                continue

            # Calculate similarity
            similarity = SequenceMatcher(None, norm1, norm2).ratio()

            # Keep high-similarity pairs (>=80%)
            if similarity >= 0.80:
                # Keep the one with longer text (more complete)
                len1 = len(txt1 or "")
                len2 = len(txt2 or "")

                if len1 > len2:
                    ids_to_remove.add(id2)
                    removal_report.append({
                        'similarity': round(similarity, 3),
                        'kept_id': id1,
                        'kept_file': fn1,
                        'kept_folder': fld1,
                        'removed_id': id2,
                        'removed_file': fn2,
                        'removed_folder': fld2,
                    })
                else:
                    ids_to_remove.add(id1)
                    removal_report.append({
                        'similarity': round(similarity, 3),
                        'kept_id': id2,
                        'kept_file': fn2,
                        'kept_folder': fld2,
                        'removed_id': id1,
                        'removed_file': fn1,
                        'removed_folder': fld1,
                    })

print(f"\nNear-duplicates found: {len(removal_report)}")
print(f"Articles to remove: {len(ids_to_remove)}")

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
        'removals': removal_report
    }

    with open("near_dedup_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\nNear-duplicates removed:")
    for item in removal_report[:15]:
        print(f"  {item['similarity']*100:.1f}% similar")
        print(f"    Kept ID {item['kept_id']}: {item['kept_file']} ({item['kept_folder']})")
        print(f"    Removed ID {item['removed_id']}: {item['removed_file']} ({item['removed_folder']})")
else:
    print("\nNo near-duplicates to remove")
