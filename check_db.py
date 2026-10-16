import sqlite3
conn = sqlite3.connect('archive.db')
cursor = conn.cursor()
cursor.execute('SELECT file_name, file_path, parsed_text FROM articles WHERE file_name LIKE "%122443%"')
row = cursor.fetchone()
if row:
    print('File Name:', row[0])
    print('File Path:', row[1])
    print('\nParsed Text (first 500 chars):')
    print(row[2][:500] if row[2] else 'EMPTY')
else:
    print('No matching record found')
conn.close()
