import pathlib
import sqlite3

base = pathlib.Path.cwd()
files = {
    path.relative_to(base).as_posix().casefold()
    for path in (base / "images").rglob("*")
    if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp", ".pdf"}
}
with sqlite3.connect(base / "archive.db") as connection:
    indexed = {
        row[0].casefold()
        for row in connection.execute("SELECT file_path FROM articles")
    }
    rows = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    pdfs = connection.execute("SELECT COUNT(*) FROM articles WHERE file_path LIKE ?", ("%.pdf",)).fetchone()[0]
    resignation = connection.execute(
        "SELECT COUNT(*) FROM articles WHERE file_path LIKE ?", ("%media clippings-Resignation%",)
    ).fetchone()[0]
    blank_text = connection.execute(
        "SELECT COUNT(*) FROM articles WHERE parsed_text IS NULL OR TRIM(parsed_text) = ''"
    ).fetchone()[0]
    missing = sorted(files - indexed)
    stale = sorted(indexed - files)
    print(f"filesystem_files={len(files)}")
    print(f"database_rows={rows}")
    print(f"database_pdf_rows={pdfs}")
    print(f"resignation_rows={resignation}")
    print(f"blank_text_rows={blank_text}")
    print(f"missing_from_database={len(missing)}")
    print(f"database_paths_not_on_disk={len(stale)}")
    if missing:
        print("first_missing=" + missing[0])
    if stale:
        print("first_stale=" + stale[0])
