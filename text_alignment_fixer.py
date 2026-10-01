import anthropic
import sqlite3
import base64
import argparse
import io
import hashlib
import os
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image
from scan_orientation import load_oriented_image

# Load API key from .env
load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not set. Create .env file with your API key.")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(PROJECT_DIR, "archive.db")
client = anthropic.Anthropic(api_key=api_key)


def resolve_image_path(file_path):
    return file_path if os.path.isabs(file_path) else os.path.join(PROJECT_DIR, file_path)


def image_digest(file_path):
    path = resolve_image_path(file_path)
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_database():
    backup_path = os.path.join(
        PROJECT_DIR,
        f"archive_pre_ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
    )
    with sqlite3.connect(db_path) as source, sqlite3.connect(backup_path) as backup:
        source.backup(backup)
    print(f"Database backup: {backup_path}", flush=True)


def deduplicate_articles():
    """Remove duplicate rows only when image bytes, filename, and folder all match."""
    with sqlite3.connect(db_path, timeout=30) as conn:
        rows = conn.execute(
            "SELECT id, file_name, folder_name, file_path FROM articles ORDER BY id"
        ).fetchall()

        groups = {}
        for article_id, file_name, folder_name, file_path in rows:
            digest = image_digest(file_path)
            if not digest:
                continue
            key = (digest, file_name.casefold(), folder_name.casefold())
            groups.setdefault(key, []).append((article_id, file_path))

        duplicate_ids = []
        for matching_rows in groups.values():
            if len(matching_rows) < 2:
                continue
            matching_rows.sort(
                key=lambda row: (
                    "[scans]_ ajay srinivisan_ 14th august" in row[1].casefold(),
                    row[0],
                )
            )
            duplicate_ids.extend(article_id for article_id, _ in matching_rows[1:])

        if duplicate_ids:
            conn.executemany("DELETE FROM articles WHERE id = ?", [(row_id,) for row_id in duplicate_ids])
            conn.commit()

    print(f"Removed {len(duplicate_ids)} verified duplicate rows", flush=True)
    return len(duplicate_ids)

def fix_text_with_image(file_name, file_path, extracted_text):
    """Use Claude vision to fix text ordering based on image layout"""

    file_path = resolve_image_path(file_path)
    if not os.path.exists(file_path):
        return extracted_text

    image = load_oriented_image(file_path)
    image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
    image_buffer = io.BytesIO()
    quality = 88
    while True:
        image_buffer.seek(0)
        image_buffer.truncate()
        image.save(image_buffer, format="JPEG", quality=quality, optimize=True)
        if image_buffer.tell() <= 7 * 1024 * 1024:
            break
        quality -= 8
        if quality < 56:
            image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
            quality = 76
    image_data = base64.standard_b64encode(image_buffer.getvalue()).decode("utf-8")

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": f"""You are correcting OCR for the scan named {file_name}.

The upright scan is the source of truth. Reconstruct the visible text in natural reading order. Keep separate columns, headlines, captions, labels, and article boundaries in their correct order. Use the OCR only to help read the scan; it may contain recognition errors and mixed reading order:

{extracted_text}

Rules:
- Only include wording supported by the scan. Never infer missing words from general knowledge.
- Correct an OCR error only when the letters are legible in the image.
- Do not summarize, modernize, or silently omit difficult passages.
- Preserve uncertain or unreadable text as [unclear] instead of guessing.
- Return only the corrected transcript, without commentary."""
                    }
                ],
            }
        ],
    )

    corrected_text = message.content[0].text.strip()
    return corrected_text or extracted_text

def process_articles(limit=None, article_id=None, dry_run=False):
    """Process articles and fix text alignment"""

    conn = sqlite3.connect(db_path, timeout=30)
    cursor = conn.cursor()

    has_raw_column = any(
        column[1] == "raw_ocr_text"
        for column in cursor.execute("PRAGMA table_info(articles)").fetchall()
    )
    if not dry_run:
        backup_database()
        if not has_raw_column:
            cursor.execute("ALTER TABLE articles ADD COLUMN raw_ocr_text TEXT")
            conn.commit()
            has_raw_column = True

    raw_column = ", raw_ocr_text" if has_raw_column else ""
    query = f"SELECT id, file_name, file_path, parsed_text{raw_column} FROM articles"
    conditions = []
    parameters = ()
    if article_id is not None:
        conditions.append("id = ?")
        parameters = (article_id,)
    elif has_raw_column:
        conditions.append("raw_ocr_text IS NULL")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"
    cursor.execute(query, parameters)
    articles = cursor.fetchall()

    if limit:
        articles = articles[:limit]

    corrected_by_image = {}
    if has_raw_column:
        completed_rows = cursor.execute(
            "SELECT file_path, parsed_text FROM articles WHERE raw_ocr_text IS NOT NULL"
        ).fetchall()
        for completed_path, completed_text in completed_rows:
            digest = image_digest(completed_path)
            if digest:
                corrected_by_image[digest] = completed_text

    updated = 0
    failed = 0
    for idx, article in enumerate(articles, 1):
        article_id, file_name, file_path, parsed_text = article[:4]
        raw_text = article[4] if has_raw_column else None
        source_text = raw_text if raw_text is not None else parsed_text or ""
        print(f"[{idx}/{len(articles)}] Processing {file_name}...", end=" ", flush=True)

        try:
            digest = image_digest(file_path)
            if digest and digest in corrected_by_image:
                fixed_text = corrected_by_image[digest]
                print("REUSED exact-image correction")
            else:
                fixed_text = fix_text_with_image(file_name, file_path, source_text)
                if digest:
                    corrected_by_image[digest] = fixed_text

            if fixed_text != source_text:
                if dry_run:
                    print(f"\n--- Proposed transcript for article {article_id} ---\n{fixed_text}\n--- End transcript ---")
                else:
                    cursor.execute(
                        "UPDATE articles SET parsed_text = ?, raw_ocr_text = ? WHERE id = ?",
                        (fixed_text, source_text, article_id),
                    )
                    conn.commit()
                    updated += 1
                    print("FIXED")
            else:
                if not dry_run:
                    cursor.execute(
                        "UPDATE articles SET raw_ocr_text = ? WHERE id = ?",
                        (source_text, article_id),
                    )
                    conn.commit()
                print("OK" if not digest or digest not in corrected_by_image else "CHECKED")
        except Exception as e:
            failed += 1
            print(f"ERROR: {e}")

    conn.close()
    print(f"\nUpdated {updated} articles")
    if not dry_run and article_id is None and limit is None and failed == 0:
        deduplicate_articles()
    elif failed:
        print(f"Kept duplicate rows because {failed} transcript corrections failed", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Correct OCR order against each scan using Claude vision.")
    parser.add_argument("--article-id", type=int, help="Process one database article ID.")
    parser.add_argument("--limit", type=int, help="Process at most this many database rows.")
    parser.add_argument("--dry-run", action="store_true", help="Print proposed text without updating the database.")
    options = parser.parse_args()
    process_articles(limit=options.limit, article_id=options.article_id, dry_run=options.dry_run)
