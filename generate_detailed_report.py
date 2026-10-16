import sqlite3
import sys
import csv
from collections import defaultdict

# Handle Unicode output
sys.stdout.reconfigure(encoding='utf-8')

db_path = "archive.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Output files
report_file = open("problematic_articles_report.txt", "w", encoding='utf-8')
csv_empty_file = open("articles_empty_text.csv", "w", encoding='utf-8', newline='')
csv_short_file = open("articles_short_text.csv", "w", encoding='utf-8', newline='')
csv_rotation_file = open("articles_with_rotation.csv", "w", encoding='utf-8', newline='')
csv_corrupted_file = open("articles_corrupted_text.csv", "w", encoding='utf-8', newline='')

def write_report(msg):
    print(msg)
    report_file.write(msg + "\n")

write_report("=" * 100)
write_report("ARCHIVE DATABASE - PROBLEMATIC ARTICLES DETAILED REPORT")
write_report(f"Generated: 2026-10-16")
write_report("=" * 100)

# Get total count
cursor.execute("SELECT COUNT(*) FROM articles")
total = cursor.fetchone()[0]
write_report(f"\nTOTAL ARTICLES IN DATABASE: {total}")

# EMPTY/NULL TEXT
write_report("\n" + "=" * 100)
write_report("1. ARTICLES WITH EMPTY/NULL PARSED_TEXT (Critical - No usable OCR data)")
write_report("=" * 100)

cursor.execute("""
    SELECT id, file_name, folder_name, file_path, LENGTH(COALESCE(parsed_text, '')) as text_length,
           LENGTH(COALESCE(raw_ocr_text, '')) as raw_length, image_rotation
    FROM articles
    WHERE parsed_text IS NULL OR TRIM(parsed_text) = ''
    ORDER BY id
""")
empty_data = cursor.fetchall()
write_report(f"\nTotal: {len(empty_data)} articles\n")

csv_writer = csv.writer(csv_empty_file)
csv_writer.writerow(['ID', 'File Name', 'Folder', 'File Path', 'Parsed Text Length', 'Raw OCR Length', 'Image Rotation'])

for id, fname, folder, fpath, tlen, raw_len, rotation in empty_data:
    write_report(f"ID {id:4d} | {fname:40s} | Folder: {folder}")
    write_report(f"         Path: {fpath}")
    write_report(f"         Parsed length: {tlen} chars | Raw OCR length: {raw_len} chars | Rotation: {rotation}")
    csv_writer.writerow([id, fname, folder, fpath, tlen, raw_len, rotation or 'None'])

# SHORT TEXT
write_report("\n" + "=" * 100)
write_report("2. ARTICLES WITH SHORT TEXT (<100 characters) - High priority")
write_report("=" * 100)

cursor.execute("""
    SELECT id, file_name, folder_name, file_path, LENGTH(COALESCE(parsed_text, '')) as text_length,
           parsed_text, image_rotation
    FROM articles
    WHERE parsed_text IS NOT NULL
      AND TRIM(parsed_text) != ''
      AND LENGTH(COALESCE(parsed_text, '')) < 100
    ORDER BY text_length ASC
""")
short_data = cursor.fetchall()
write_report(f"\nTotal: {len(short_data)} articles\n")

csv_writer = csv.writer(csv_short_file)
csv_writer.writerow(['ID', 'File Name', 'Folder', 'Text Length', 'Text Preview', 'Image Rotation'])

for id, fname, folder, fpath, tlen, text, rotation in short_data:
    text_preview = (text[:60] if text else "").replace('\n', ' ')
    write_report(f"ID {id:4d} | {fname:40s} | {tlen:3d} chars")
    write_report(f"         Folder: {folder}")
    write_report(f"         Text: {text_preview}")
    csv_writer.writerow([id, fname, folder, tlen, text, rotation or 'None'])

# IMAGE ROTATION ISSUES
write_report("\n" + "=" * 100)
write_report("3. ARTICLES WITH IMAGE ROTATION (Already manually fixed)")
write_report("=" * 100)

cursor.execute("""
    SELECT id, file_name, folder_name, file_path, image_rotation,
           LENGTH(COALESCE(parsed_text, '')) as text_length
    FROM articles
    WHERE image_rotation IS NOT NULL AND image_rotation != 0
    ORDER BY image_rotation, id
""")
rotation_data = cursor.fetchall()
write_report(f"\nTotal: {len(rotation_data)} articles\n")

rotation_breakdown = defaultdict(list)
for row in rotation_data:
    rotation_breakdown[row[4]].append(row)

csv_writer = csv.writer(csv_rotation_file)
csv_writer.writerow(['ID', 'File Name', 'Folder', 'File Path', 'Rotation Angle', 'Text Length'])

for angle in sorted(rotation_breakdown.keys()):
    articles = rotation_breakdown[angle]
    write_report(f"\nRotation angle: {angle}° ({len(articles)} articles)")
    for id, fname, folder, fpath, rotation, tlen in articles:
        write_report(f"  ID {id:4d} | {fname:40s} | {folder:30s} | Text: {tlen} chars")
        csv_writer.writerow([id, fname, folder, fpath, angle, tlen])

# CORRUPTED/GARBLED TEXT
write_report("\n" + "=" * 100)
write_report("4. ARTICLES WITH POTENTIALLY CORRUPTED TEXT")
write_report("=" * 100)

cursor.execute("""
    SELECT id, file_name, folder_name, file_path, parsed_text, LENGTH(COALESCE(parsed_text, '')) as text_length
    FROM articles
    WHERE parsed_text IS NOT NULL AND LENGTH(COALESCE(parsed_text, '')) > 0
""")
all_articles = cursor.fetchall()

corrupted = []
for id, fname, folder, fpath, ptext, tlen in all_articles:
    issues = []

    if ptext:
        # Check for excessive special characters
        special_ratio = sum(1 for c in ptext if ord(c) < 32 or ord(c) > 126) / len(ptext)
        if special_ratio > 0.1:
            issues.append("excessive_special_chars")

        # Check for repeated characters
        if any(ptext.count(c*10) > 0 for c in 'abcdefghijklmnopqrstuvwxyz'):
            issues.append("repeated_chars")

        # Check for very high ratio of numbers to letters
        if len(ptext) > 20:
            alpha_count = sum(1 for c in ptext if c.isalpha())
            if alpha_count > 0 and (len(ptext) - alpha_count) / len(ptext) > 0.7:
                issues.append("mostly_numbers_symbols")

    if issues:
        corrupted.append((id, fname, folder, fpath, issues, tlen, ptext))

write_report(f"\nTotal: {len(corrupted)} articles with corruption indicators\n")

csv_writer = csv.writer(csv_corrupted_file)
csv_writer.writerow(['ID', 'File Name', 'Folder', 'File Path', 'Issues', 'Text Length'])

for id, fname, folder, fpath, issues, tlen, ptext in corrupted:
    write_report(f"ID {id:4d} | {fname:40s} | {tlen:5d} chars")
    write_report(f"         Folder: {folder}")
    write_report(f"         Issues: {', '.join(issues)}")
    csv_writer.writerow([id, fname, folder, fpath, '|'.join(issues), tlen])

# SUMMARY BY FOLDER
write_report("\n" + "=" * 100)
write_report("5. SUMMARY BY FOLDER/ERA")
write_report("=" * 100)

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

write_report(f"\n{'Folder':<35} | {'Total':>6} | {'Empty':>6} | {'Short':>6} | {'Rotated':>6} | {'Problematic %':>12}")
write_report("-" * 90)

for folder, total, empty, short, rotated in folder_stats:
    empty = empty or 0
    short = short or 0
    rotated = rotated or 0
    problematic = empty + short + rotated
    pct = (problematic / total * 100) if total > 0 else 0
    write_report(f"{folder:<35} | {total:>6} | {empty:>6} | {short:>6} | {rotated:>6} | {pct:>11.1f}%")

# RECOMMENDATIONS
write_report("\n" + "=" * 100)
write_report("6. RECOMMENDATIONS & ACTION PLAN")
write_report("=" * 100)

write_report(f"\n[PRIORITY 1] CRITICAL - Empty parsed_text (0 characters usable)")
write_report(f"  Count: {len(empty_data)} article(s)")
write_report(f"  Action:")
write_report(f"    - These articles have NO OCR data extracted")
write_report(f"    - Check if source image files still exist")
write_report(f"    - Re-scan with OCR (Claude Vision or alternative OCR tool)")
write_report(f"    - Investigate why initial OCR failed")
if empty_data:
    write_report(f"  Article IDs: {', '.join(str(row[0]) for row in empty_data)}")

write_report(f"\n[PRIORITY 2] HIGH - Short text (<100 characters)")
write_report(f"  Count: {len(short_data)} article(s)")
write_report(f"  Action:")
write_report(f"    - These articles likely had OCR failures")
write_report(f"    - Check source image quality and resolution")
write_report(f"    - Re-scan with higher quality settings")
write_report(f"    - Consider manual transcription if source is clear")
if short_data:
    write_report(f"  Article IDs: {', '.join(str(row[0]) for row in short_data)}")

write_report(f"\n[PRIORITY 3] MEDIUM - Image rotation issues (Already manually fixed)")
write_report(f"  Count: {len(rotation_data)} article(s)")
write_report(f"  Action:")
write_report(f"    - These images required manual rotation to be readable")
write_report(f"    - Consider fixing source images to prevent future re-scanning")
write_report(f"    - Monitor for any re-occurrence of rotation issues")
write_report(f"    - Rotation breakdown: 90°={len(rotation_breakdown[90])}, 180°={len(rotation_breakdown[180])}, 270°={len(rotation_breakdown[270])}")

write_report(f"\n[PRIORITY 4] MEDIUM - Potentially corrupted text")
write_report(f"  Count: {len(corrupted)} article(s)")
write_report(f"  Action:")
write_report(f"    - Manual review needed to confirm corruption")
write_report(f"    - May be due to:")
write_report(f"      - Non-ASCII text encoding (Hindi, Chinese, Gujarati, etc.)")
write_report(f"      - Mixed language documents")
write_report(f"      - Poor OCR quality with special characters")
write_report(f"    - Consider re-OCR with language-specific models")

total_problematic = len(empty_data) + len(short_data) + len(rotation_data) + len(corrupted)
pct_problematic = (total_problematic / total) * 100 if total > 0 else 0

write_report(f"\n" + "=" * 100)
write_report(f"OVERALL SUMMARY")
write_report("=" * 100)
write_report(f"Total articles: {total}")
write_report(f"Problematic articles: {total_problematic} ({pct_problematic:.1f}%)")
write_report(f"  - Empty/null text: {len(empty_data)}")
write_report(f"  - Short text (<100 chars): {len(short_data)}")
write_report(f"  - Image rotation issues: {len(rotation_data)}")
write_report(f"  - Corrupted/suspicious text: {len(corrupted)}")
write_report(f"\nDatabase health: {'GOOD' if pct_problematic < 5 else 'FAIR' if pct_problematic < 10 else 'NEEDS ATTENTION'}")

write_report("\n" + "=" * 100)
write_report("Generated output files:")
write_report("  - articles_empty_text.csv")
write_report("  - articles_short_text.csv")
write_report("  - articles_with_rotation.csv")
write_report("  - articles_corrupted_text.csv")
write_report("  - problematic_articles_report.txt")
write_report("=" * 100)

# Close all files
report_file.close()
csv_empty_file.close()
csv_short_file.close()
csv_rotation_file.close()
csv_corrupted_file.close()

print("\n✓ Report files generated successfully")
