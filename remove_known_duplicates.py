import sqlite3
from pathlib import Path
import json

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Known duplicates: keep the one with longer text
# Format: (keep_id, remove_id, reason)
known_duplicates = [
    (197, 1625, "LDC debt – a booming secondary market (7819 vs 6562 chars)"),
]

# Fetch the IDs to verify before removal
to_remove = []
for keep_id, remove_id, reason in known_duplicates:
    cursor.execute("SELECT id, file_name, parsed_text FROM articles WHERE id IN (?, ?)", (keep_id, remove_id))
    rows = cursor.fetchall()

    if len(rows) == 2:
        kept = rows[0] if rows[0][0] == keep_id else rows[1]
        removed = rows[1] if rows[0][0] == keep_id else rows[0]

        print(f"Keeping ID {keep_id}: {kept[1]} ({len(kept[2] or '')} chars)")
        print(f"Removing ID {remove_id}: {removed[1]} ({len(removed[2] or '')} chars)")
        print(f"Reason: {reason}\n")

        to_remove.append(remove_id)

if to_remove:
    placeholders = ",".join("?" * len(to_remove))
    cursor.execute(f"DELETE FROM articles WHERE id IN ({placeholders})", to_remove)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM articles")
    final_count = cursor.fetchone()[0]

    print(f"Removed {len(to_remove)} articles")
    print(f"Final count: {final_count}")

    # Save report
    report = {
        "removed_count": len(to_remove),
        "final_count": final_count,
        "removed_ids": to_remove,
        "details": [
            {
                "reason": reason,
                "kept_id": keep_id,
                "removed_id": remove_id
            }
            for keep_id, remove_id, reason in known_duplicates
        ]
    }

    with open("remove_known_duplicates_report.json", "w") as f:
        json.dump(report, f, indent=2)

conn.close()
