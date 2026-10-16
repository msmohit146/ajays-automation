import sqlite3

conn = sqlite3.connect('archive.db')
c = conn.cursor()

# Test various searches
test_words = ['bank', 'India', 'financial', 'ICICI', 'market', 'stock', 'economy']

print("Testing search functionality:\n")
for word in test_words:
    c.execute(f"SELECT COUNT(*) FROM articles WHERE LOWER(parsed_text) LIKE LOWER(?)", (f'%{word}%',))
    result = c.fetchone()[0]
    print(f'Results for "{word}": {result}')

conn.close()
