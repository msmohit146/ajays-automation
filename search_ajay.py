import sqlite3
import os

if not os.path.exists('archive.db'):
    print("Database file not created yet - still starting...")
    exit()

try:
    conn = sqlite3.connect('archive.db', timeout=5)
    cursor = conn.cursor()

    # Count total articles
    cursor.execute('SELECT COUNT(*) FROM articles')
    total = cursor.fetchone()[0]

    # Count articles with "Ajay"
    cursor.execute('SELECT COUNT(*) FROM articles WHERE parsed_text LIKE "%Ajay%" OR parsed_text LIKE "%ajay%"')
    ajay_count = cursor.fetchone()[0]

    # Count articles with "Srinivasan"
    cursor.execute('SELECT COUNT(*) FROM articles WHERE parsed_text LIKE "%Srinivasan%" OR parsed_text LIKE "%srinivasan%"')
    srinivasan_count = cursor.fetchone()[0]

    # Count articles with both
    cursor.execute('SELECT COUNT(*) FROM articles WHERE (parsed_text LIKE "%Ajay%" OR parsed_text LIKE "%ajay%") AND (parsed_text LIKE "%Srinivasan%" OR parsed_text LIKE "%srinivasan%")')
    both_count = cursor.fetchone()[0]

    print(f"\n📊 DATABASE PROGRESS & AJAY SRINIVASAN MENTIONS")
    print("=" * 50)
    print(f"Database Status: {total}/820 articles processed ({(total/820)*100:.1f}%)")
    print(f"\n Mentions Found So Far:")
    print(f"  ✓ 'Ajay': {ajay_count} articles")
    print(f"  ✓ 'Srinivasan': {srinivasan_count} articles")
    print(f"  ✓ Both 'Ajay' AND 'Srinivasan': {both_count} articles")
    print("\n(Will update with final count once rebuild completes)")

    conn.close()
except Exception as e:
    print(f"Database still building... Error: {e}")
