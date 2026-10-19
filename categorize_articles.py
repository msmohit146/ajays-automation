#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path('archive.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Define 20 topics with their keywords
topics = {
    'Banking & Financial Services': ['bank', 'banking', 'financial services', 'aditya birla', 'insurance', 'credit', 'loan', 'mortgage'],
    'Budget & Fiscal Policy': ['budget', 'fiscal', 'tax', 'taxation', 'deficit', 'gdp', 'revenue', 'government spending'],
    'Stock Markets & Trading': ['stock', 'market', 'nifty', 'sensex', 'trading', 'shares', 'equity', 'investment'],
    'Infrastructure & Development': ['infrastructure', 'highways', 'roads', 'railways', 'ports', 'development', 'construction'],
    'Interest Rates & Monetary Policy': ['interest rate', 'rbi', 'monetary', 'inflation', 'reserve bank', 'rbi governor'],
    'Pension & Retirement': ['pension', 'retirement', 'nps', 'social security', 'provident fund'],
    'Insurance Industry': ['insurance', 'life insurance', 'health insurance', 'premiums', 'coverage', 'claims'],
    'Economic Growth': ['growth', 'economy', 'economic', 'development', 'gdp', 'expansion', 'recovery'],
    'Employment & Wages': ['employment', 'wages', 'salary', 'jobs', 'unemployment', 'labor', 'workforce'],
    'Corporate Performance': ['corporate', 'company', 'business', 'performance', 'profit', 'revenue', 'operations'],
    'Real Estate & Property': ['real estate', 'property', 'housing', 'land', 'real estate investment'],
    'Commodities & Futures': ['commodity', 'commodities', 'futures', 'gold', 'silver', 'agricultural'],
    'Retail & Consumer': ['retail', 'consumer', 'consumption', 'demand', 'spending', 'shopping'],
    'Technology & Innovation': ['technology', 'digital', 'innovation', 'tech', 'it sector'],
    'Trade & Exports': ['trade', 'exports', 'imports', 'commerce', 'tariff', 'global trade'],
    'Energy & Power': ['energy', 'power', 'electricity', 'coal', 'renewable', 'oil'],
    'Healthcare & Pharmaceuticals': ['healthcare', 'pharmaceuticals', 'health', 'medical', 'drugs', 'hospitals'],
    'Education & Skills': ['education', 'skills', 'training', 'universities', 'institutions', 'learning'],
    'Regulation & Compliance': ['regulation', 'compliance', 'norms', 'rules', 'legal', 'act', 'guidelines'],
    'Foreign Investment & FDI': ['foreign investment', 'fdi', 'foreign direct', 'international', 'overseas'],
}

print('Categorizing articles by topic...\n')

cursor.execute('SELECT id, parsed_text FROM articles WHERE parsed_text IS NOT NULL')
articles = cursor.fetchall()

topic_counts = {topic: 0 for topic in topics}
unmatched = 0

for article_id, text in articles:
    text_lower = text.lower()
    assigned_topic = None

    # Find the best matching topic
    for topic, keywords in topics.items():
        if any(keyword in text_lower for keyword in keywords):
            assigned_topic = topic
            topic_counts[topic] += 1
            break

    if assigned_topic:
        cursor.execute('UPDATE articles SET topic = ? WHERE id = ?', (assigned_topic, article_id))
    else:
        unmatched += 1

    if article_id % 50 == 0:
        print(f'Processed {article_id} articles...')

conn.commit()

print(f'\nCategorization complete!')
print(f'\nTopic breakdown:')
print('-' * 60)
for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
    print(f'{topic}: {count} articles')
print('-' * 60)
print(f'Unmatched: {unmatched} articles')

conn.close()
