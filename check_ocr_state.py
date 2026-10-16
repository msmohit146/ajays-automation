import sqlite3

with sqlite3.connect("archive.db") as connection:
    print("rows=" + str(connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]))
    print("raw_nonnull=" + str(connection.execute("SELECT COUNT(*) FROM articles WHERE raw_ocr_text IS NOT NULL").fetchone()[0]))
    print("parsed_nonblank=" + str(connection.execute("SELECT COUNT(*) FROM articles WHERE parsed_text IS NOT NULL AND TRIM(parsed_text) <> ''").fetchone()[0]))
    print("blank=" + str(connection.execute("SELECT COUNT(*) FROM articles WHERE parsed_text IS NULL OR TRIM(parsed_text) = ''").fetchone()[0]))
    print("new_image_rows=" + str(connection.execute("SELECT COUNT(*) FROM articles WHERE file_path LIKE ?", ("%.jpg",)).fetchone()[0]))
    print("new_pdf_rows=" + str(connection.execute("SELECT COUNT(*) FROM articles WHERE file_path LIKE ?", ("%.pdf",)).fetchone()[0]))
