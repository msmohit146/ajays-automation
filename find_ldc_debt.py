import sqlite3
import re

def extract_title(text):
    """Extract the first meaningful line as title."""
    if not text:
        return None
    lines = text.strip().split('\n')
    for line in lines:
        clean = line.strip()
        if clean and len(clean) > 5:
            return clean.casefold()
    return None

db_path = "archive.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Search for LDC debt articles
cursor.execute("""
    SELECT id, file_name, folder_name, file_path, parsed_text
    FROM articles
    WHERE parsed_text LIKE '%LDC debt%' OR parsed_text LIKE '%booming secondary%'
    ORDER BY id
""")
articles = cursor.fetchall()
conn.close()

print(f"Found {len(articles)} articles mentioning 'LDC debt' or 'booming secondary'\n")

for article_id, file_name, folder_name, file_path, parsed_text in articles:
    title = extract_title(parsed_text)
    text_preview = parsed_text[:200] if parsed_text else "NO TEXT"
    text_len = len(parsed_text or "")

    print(f"ID {article_id}: {file_name} ({folder_name})")
    print(f"  Title: {title}")
    print(f"  Text length: {text_len}")
    print(f"  Preview: {text_preview}...")
    print()

# Also check if they have the same normalized text (when punctuation removed)
print("\n=== CHECKING TEXT SIMILARITY ===\n")

def normalize_for_comparison(text):
    """Remove all punctuation and extra whitespace."""
    text = (text or "").lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()
    return text

if len(articles) > 1:
    for i, article1 in enumerate(articles):
        for article2 in articles[i+1:]:
            id1, fn1, fld1, fp1, txt1 = article1
            id2, fn2, fld2, fp2, txt2 = article2

            norm1 = normalize_for_comparison(txt1)
            norm2 = normalize_for_comparison(txt2)

            if norm1 and norm2:
                # Calculate how similar they are
                from difflib import SequenceMatcher
                ratio = SequenceMatcher(None, norm1, norm2).ratio()
                print(f"ID {id1} vs ID {id2}: {ratio*100:.1f}% similar")
