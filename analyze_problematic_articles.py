import sqlite3
import json
import sys
from collections import defaultdict

# Handle Unicode output
sys.stdout.reconfigure(encoding='utf-8')

db_path = "archive.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Initialize report structure
report = {
    "summary": {},
    "by_category": {},
    "by_folder": defaultdict(lambda: defaultdict(list)),
    "specific_issues": {}
}

print("=" * 80)
print("ARCHIVE DATABASE ANALYSIS REPORT")
print("=" * 80)

# 1. Overall statistics
cursor.execute("SELECT COUNT(*) FROM articles")
total_articles = cursor.fetchone()[0]
print(f"\n[1] TOTAL ARTICLES IN DATABASE: {total_articles}")

# 2. Articles with EMPTY or NULL parsed_text
cursor.execute("""
    SELECT id, file_name, folder_name, LENGTH(COALESCE(parsed_text, '')) as text_length
    FROM articles
    WHERE parsed_text IS NULL OR TRIM(parsed_text) = ''
    ORDER BY id
""")
empty_text = cursor.fetchall()
print(f"\n[2] ARTICLES WITH EMPTY/NULL PARSED_TEXT: {len(empty_text)}")
if empty_text:
    print("    Sample (first 10):")
    for row in empty_text[:10]:
        print(f"      ID {row[0]:4d} | {row[3]:5d} chars | {row[1][:40]:40s} | {row[2]}")

report["summary"]["empty_parsed_text"] = len(empty_text)
report["by_category"]["empty_parsed_text"] = [row[0] for row in empty_text]
for id, fname, folder, _ in empty_text:
    report["by_folder"][folder]["empty_parsed_text"].append(id)

# 3. Articles with VERY SHORT text (< 100 characters)
cursor.execute("""
    SELECT id, file_name, folder_name, LENGTH(COALESCE(parsed_text, '')) as text_length
    FROM articles
    WHERE parsed_text IS NOT NULL
      AND TRIM(parsed_text) != ''
      AND LENGTH(COALESCE(parsed_text, '')) < 100
    ORDER BY text_length ASC
""")
short_text = cursor.fetchall()
print(f"\n[3] ARTICLES WITH SHORT TEXT (<100 chars): {len(short_text)}")
if short_text:
    print("    Top 10 shortest:")
    for row in short_text[:10]:
        text_preview = row[1][:35] if row[1] else "(no text)"
        print(f"      ID {row[0]:4d} | {row[3]:3d} chars | {row[2]:25s} | {text_preview}")

report["summary"]["short_text"] = len(short_text)
report["by_category"]["short_text"] = [row[0] for row in short_text]
for id, fname, folder, _ in short_text:
    report["by_folder"][folder]["short_text"].append(id)

# 4. Articles with IMAGE ROTATION issues (manually fixed)
cursor.execute("""
    SELECT id, file_name, folder_name, image_rotation
    FROM articles
    WHERE image_rotation IS NOT NULL AND image_rotation != 0
    ORDER BY image_rotation
""")
rotation_issues = cursor.fetchall()
print(f"\n[4] ARTICLES WITH IMAGE ROTATION (manually fixed): {len(rotation_issues)}")
if rotation_issues:
    rotation_breakdown = defaultdict(list)
    for id, fname, folder, rotation in rotation_issues:
        rotation_breakdown[rotation].append((id, folder, fname))
    print("    Breakdown by rotation angle:")
    for angle in sorted(rotation_breakdown.keys()):
        print(f"      {angle}°: {len(rotation_breakdown[angle])} articles")
        for id, folder, fname in rotation_breakdown[angle][:5]:
            print(f"        ID {id:4d} | {folder:25s} | {fname[:35]}")

report["summary"]["rotation_issues"] = len(rotation_issues)
report["by_category"]["rotation_issues"] = [row[0] for row in rotation_issues]
for id, fname, folder, _ in rotation_issues:
    report["by_folder"][folder]["rotation_issues"].append(id)

# 5. Articles with POTENTIAL CORRUPTED/GARBLED TEXT
# Look for common corruption patterns
cursor.execute("""
    SELECT id, file_name, folder_name, parsed_text, LENGTH(COALESCE(parsed_text, '')) as text_length
    FROM articles
    WHERE parsed_text IS NOT NULL
      AND LENGTH(COALESCE(parsed_text, '')) > 0
""")
all_articles = cursor.fetchall()

corrupted = []
for id, fname, folder, ptext, tlen in all_articles:
    # Detect corruption patterns
    issues = []

    # Check for excessive special characters or control characters
    if ptext:
        special_ratio = sum(1 for c in ptext if ord(c) < 32 or ord(c) > 126) / len(ptext)
        if special_ratio > 0.1:  # More than 10% non-printable characters
            issues.append("excessive_special_chars")

        # Check for repeated characters (likely OCR error)
        if any(ptext.count(c*10) > 0 for c in 'abcdefghijklmnopqrstuvwxyz'):
            issues.append("repeated_chars")

        # Check for very high ratio of numbers to letters (garbled data)
        if len(ptext) > 20:
            alpha_count = sum(1 for c in ptext if c.isalpha())
            if alpha_count > 0 and (len(ptext) - alpha_count) / len(ptext) > 0.7:
                issues.append("mostly_numbers_symbols")

    if issues:
        corrupted.append((id, fname, folder, issues, tlen, ptext[:100]))

print(f"\n[5] ARTICLES WITH POTENTIALLY CORRUPTED TEXT: {len(corrupted)}")
if corrupted:
    print("    Details:")
    for id, fname, folder, issues, tlen, preview in corrupted[:15]:
        # Clean preview for safe printing
        try:
            safe_preview = preview.encode('utf-8', errors='replace').decode('utf-8')
        except:
            safe_preview = "[encoding error]"
        print(f"      ID {id:4d} | {tlen:5d} chars | {folder:25s}")
        print(f"        Issues: {', '.join(issues)}")
        print(f"        Preview: {safe_preview}...")

report["summary"]["corrupted_text"] = len(corrupted)
report["by_category"]["corrupted_text"] = [row[0] for row in corrupted]
for id, fname, folder, _, _, _ in corrupted:
    report["by_folder"][folder]["corrupted_text"].append(id)

# 6. TEXT LENGTH DISTRIBUTION
cursor.execute("""
    SELECT
        CASE
            WHEN parsed_text IS NULL OR TRIM(parsed_text) = '' THEN '0_empty'
            WHEN LENGTH(parsed_text) < 100 THEN '1_0-100_chars'
            WHEN LENGTH(parsed_text) < 500 THEN '2_100-500_chars'
            WHEN LENGTH(parsed_text) < 1000 THEN '3_500-1k_chars'
            WHEN LENGTH(parsed_text) < 5000 THEN '4_1k-5k_chars'
            ELSE '5_5k+_chars'
        END as length_range,
        COUNT(*) as count
    FROM articles
    GROUP BY length_range
    ORDER BY length_range
""")
length_dist = cursor.fetchall()
print(f"\n[6] TEXT LENGTH DISTRIBUTION:")
for range_label, count in length_dist:
    pct = (count / total_articles) * 100
    print(f"    {range_label:20s}: {count:5d} ({pct:5.1f}%)")

# 7. FOLDER/ERA BREAKDOWN
cursor.execute("""
    SELECT folder_name, COUNT(*) as total,
           SUM(CASE WHEN parsed_text IS NULL OR TRIM(parsed_text) = '' THEN 1 ELSE 0 END) as empty,
           SUM(CASE WHEN parsed_text IS NOT NULL AND LENGTH(parsed_text) < 100 THEN 1 ELSE 0 END) as short,
           SUM(CASE WHEN image_rotation IS NOT NULL AND image_rotation != 0 THEN 1 ELSE 0 END) as rotated
    FROM articles
    GROUP BY folder_name
    ORDER BY total DESC
""")
folder_stats = cursor.fetchall()
print(f"\n[7] BREAKDOWN BY FOLDER/ERA:")
print(f"    {'Folder':30s} | {'Total':6s} | {'Empty':6s} | {'Short':6s} | {'Rotated':6s}")
print(f"    {'-'*30}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}")
for folder, total, empty, short, rotated in folder_stats:
    empty = empty or 0
    short = short or 0
    rotated = rotated or 0
    print(f"    {folder:30s} | {total:6d} | {empty:6d} | {short:6d} | {rotated:6d}")

# 8. RECOMMENDATIONS
print(f"\n[8] RECOMMENDED NEXT STEPS:")
print(f"\n    Priority 1 - CRITICAL (No usable text):")
print(f"      • {len(empty_text)} articles with empty/null parsed_text")
print(f"        Action: Re-scan these articles from source images")

print(f"\n    Priority 2 - HIGH (Minimal text, likely OCR failure):")
print(f"      • {len(short_text)} articles with <100 characters")
print(f"        Action: Review OCR quality, may need re-scanning or manual correction")

if rotation_issues:
    print(f"\n    Priority 3 - MEDIUM (Image issues, already manually fixed):")
    print(f"      • {len(rotation_issues)} articles with rotation fixes applied")
    print(f"        Action: Monitor for re-occurrence; consider source image adjustment")

if corrupted:
    print(f"\n    Priority 4 - MEDIUM (Potential corruption detected):")
    print(f"      • {len(corrupted)} articles with suspicious text patterns")
    print(f"        Action: Manual review of samples; may indicate OCR or import issues")

total_problematic = len(empty_text) + len(short_text) + len(corrupted) + len(rotation_issues)
print(f"\n    TOTAL PROBLEMATIC ARTICLES: {total_problematic} ({(total_problematic/total_articles)*100:.1f}%)")

conn.close()
print("\n" + "=" * 80)
