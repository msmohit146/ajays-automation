import sqlite3

with sqlite3.connect('archive.db') as c:
    for start, end in [(1, 900), (850, 1000), (1500, 1665), (1650, 1750), (2000, 2200), (2200, 2380)]:
        rows = c.execute('SELECT id, file_name, file_path FROM articles WHERE id BETWEEN ? AND ? ORDER BY id LIMIT 5', (start, end)).fetchall()
        count = c.execute('SELECT COUNT(*) FROM articles WHERE id BETWEEN ? AND ?', (start, end)).fetchone()[0]
        print(f'range={start}-{end} count={count}')
        for row in rows:
            print(f'  {row[0]} {row[1]} {row[2]}')
