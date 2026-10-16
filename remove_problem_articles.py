import sqlite3
from pathlib import Path
import json

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# PDF entries to remove (55 total)
pdf_ids = [1569, 1570, 1571, 1572, 1573, 1574, 1575, 1576, 1577, 1578, 1579, 1580, 1581, 1582, 1583, 1584, 1585, 1586, 1587, 1588]

# Get all PDF IDs
cursor.execute("SELECT id FROM articles WHERE file_path LIKE '%.pdf%' OR file_name LIKE '%.pdf%'")
all_pdf_ids = [row[0] for row in cursor.fetchall()]

# Garbled OCR articles to remove (18 total)
garbled_ids = [150, 151, 152, 153, 154, 155, 156, 676, 1541, 1542, 1543, 1544, 1545, 1546, 1548, 1549, 2022, 2051]

ids_to_remove = list(set(all_pdf_ids + garbled_ids))
ids_to_remove.sort()

print(f"Removing {len(ids_to_remove)} problematic articles:")
print(f"  - {len(all_pdf_ids)} PDF entries")
print(f"  - {len(garbled_ids)} articles with garbled OCR")

# Get details before removal
cursor.execute("SELECT id, file_name FROM articles WHERE id IN ({})".format(
    ",".join("?" * len(ids_to_remove))
), ids_to_remove)
articles_to_remove = cursor.fetchall()

# Remove articles
placeholders = ",".join("?" * len(ids_to_remove))
cursor.execute(f"DELETE FROM articles WHERE id IN ({placeholders})", ids_to_remove)
conn.commit()

# Get final count
cursor.execute("SELECT COUNT(*) FROM articles")
final_count = cursor.fetchone()[0]

print(f"\nRemoved {len(ids_to_remove)} articles")
print(f"New article count: {final_count}")

# Save report
report = {
    "removed_count": len(ids_to_remove),
    "pdf_removed": len(all_pdf_ids),
    "garbled_ocr_removed": len(garbled_ids),
    "final_count": final_count,
    "removed_ids": ids_to_remove,
    "removed_files": [f"{aid}: {fname}" for aid, fname in articles_to_remove[:20]]
}

with open("remove_problem_articles_report.json", "w") as f:
    json.dump(report, f, indent=2)

print("\nExamples of removed files:")
for aid, fname in articles_to_remove[:15]:
    print(f"  ID {aid}: {fname}")

conn.close()
