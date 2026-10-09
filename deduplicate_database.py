import sqlite3
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import shutil

def extract_title(text):
    """Extract the first line (likely the article title)."""
    if not text:
        return None
    lines = text.strip().split('\n')
    for line in lines:
        clean = line.strip()
        if clean and len(clean) > 5:
            return clean.casefold()
    return None

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
        score += (2030 - year)  # Earlier years get higher score
    except (ValueError, IndexError):
        score += 1000  # Non-year folders get bonus

    # Prefer longer OCR text (more complete)
    text_len = len(parsed_text or "")
    score += min(text_len // 100, 50)  # Bonus for length, capped at 50

    return score, article

db_path = Path("archive.db")
backup_path = Path(f"archive_dedup_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")

# Backup database first
shutil.copy(db_path, backup_path)
print(f"Backup created: {backup_path}")

# Load all articles
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("""
    SELECT id, file_name, folder_name, file_path, parsed_text
    FROM articles
    ORDER BY id
""")
articles = cursor.fetchall()
conn.close()

print(f"Total articles before dedup: {len(articles)}")

# Group by title
title_groups = defaultdict(list)
for article in articles:
    title = extract_title(article[4])
    if title:
        title_groups[title].append(article)

# Identify duplicates and choose which to keep
duplicate_groups = {k: v for k, v in title_groups.items() if len(v) > 1}
ids_to_remove = []
cleanup_report = {
    "backup": str(backup_path),
    "timestamp": datetime.now().isoformat(),
    "duplicate_groups": len(duplicate_groups),
    "rows_to_remove": 0,
    "groups": []
}

for title, group in sorted(duplicate_groups.items()):
    # Score each article and keep the best one
    scored = [score_article(article) for article in group]
    scored.sort(reverse=True)

    best_score, best_article = scored[0]
    kept_id = best_article[0]
    kept_path = best_article[3]

    # All others should be removed
    removed_ids = [article[0] for score, article in scored[1:]]
    ids_to_remove.extend(removed_ids)

    cleanup_report["groups"].append({
        "kept_id": kept_id,
        "kept_path": kept_path,
        "title": title[:100],
        "removed_ids": removed_ids,
        "group_size": len(group)
    })

cleanup_report["rows_to_remove"] = len(ids_to_remove)

# Remove duplicates from database
if ids_to_remove:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    placeholders = ",".join("?" * len(ids_to_remove))
    cursor.execute(f"DELETE FROM articles WHERE id IN ({placeholders})", ids_to_remove)
    conn.commit()

    # Get final count
    cursor.execute("SELECT COUNT(*) FROM articles")
    final_count = cursor.fetchone()[0]
    conn.close()

    cleanup_report["final_count"] = final_count

    print(f"\nRemoved {len(ids_to_remove)} duplicate articles")
    print(f"Total articles after dedup: {final_count}")
else:
    print("No duplicates to remove")

# Save report
report_path = Path("dedup_report.json")
with open(report_path, "w") as f:
    json.dump(cleanup_report, f, indent=2)

print(f"\nDetailed report saved to: {report_path}")
print(f"\nTop duplicates removed:")
for i, group in enumerate(cleanup_report["groups"][:10]):
    print(f"  {i+1}. {group['title']}: removed {len(group['removed_ids'])} copies (kept ID {group['kept_id']})")
