import sqlite3
from pathlib import Path

# Properly formatted text extracted from the image, reading columns left to right
corrected_text = """THE ASIAN WALL
Vol. XVIII No. 5                                                                    TUESDAY, SE

—What's News—

World-Wide
NORTH KOREA ASKED South Korea to make a commitment to discontinue joint military exercises with the U.S. before reopening inter-Korea dialogue. Pyongyang also asked that Seoul halt its joint efforts with the U.S. and Japan to pressure the communist North to resolve suspicions about its nuclear program, but stopped short of saying the demands were a condition for reopening talks.

Israel will allow six deported PLO activists to return to the occupied territories, the Israeli army said. The move comes amid a flurry of Israeli-Palestinian contacts to resolve differences delaying the signing of a peace accord. Syria and Lebanon, meanwhile, said they saw no progress on their own problems at peace talks in Washington.

Italy agreed to delay indefinitely the pullout from Mogadishu of the last few hundred troops of its 2,400-member contingent. The move was a result of the deteriorating security situation in Somalia and the failure of the UN to assume full responsibility for the troubled East African nation.

Business and Finance
TOSHIBA WILL CUT its parent company work force by 6.6% through attrition, a plan the firm ascribed to a shift toward higher-value-added products that require few workers to make. But analysts say it looks like an effort to cut costs.

IBM will unveil specialized PC packages today, including a collection of high-end notebook models, with built-in multimedia features as Intel carbon-fiber cases and optional electronics to make their color screens display videocassette or TV-broadcast signals.

Renault and Volvo unveiled their long-awaited merger plan – moving to create one of Europe's biggest industrial companies, but leaving ownership much more finely balanced than most analysts had expected.

Foreign Finance
Rush Into In
By SUMAN DUBEY
Staff Reporter

BOMBAY – As India gradually cuts financial markets loose from a bureaucratic straitjacket, foreign financial institutions are scurrying to set up joint ventures and alliances with Indian companies. "I think there's a very good opportunity to create a profitable business of substantial size," says Timothy Brenner, a partner of Asian Capital Partners, Hong Kong. That firm recently formed a joint venture with state-owned Industrial Development Bank of India to provide investment-banking services.

The surge of foreign interest is largely due to financial deregulation, since the beginning of this year, banks have been allowed to set their own interest rates on loans of more than 200,000 rupees ($6,420), subject to a minimum rate. Currently, 15%. The private sector has been permitted to provide more banking services and operate mutual funds, while the stock market has been opened wider to foreign investors.

Many foreigners still find doing business in India highly frustrating. Moreover, India's financial reforms were slowed by last-minute government resistance. Still, once India opens its capital account – expected sometime next year – foreign financial institutions are likely to find India a far more attractive market.

(Story on Page 5)

(Story on Page 7)
"""

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Update article ID 221 with corrected text
cursor.execute("""
    UPDATE articles
    SET parsed_text = ?
    WHERE id = 221
""", (corrected_text,))

conn.commit()

# Verify the update
cursor.execute("SELECT id, file_name, parsed_text FROM articles WHERE id = 221")
result = cursor.fetchone()
conn.close()

if result:
    article_id, file_name, text = result
    print(f"✓ Updated article ID {article_id}")
    print(f"  File: {file_name}")
    print(f"  New text length: {len(text)} chars")
    print(f"\nFirst 300 chars of corrected text:")
    print(text[:300])
else:
    print("Failed to update article")
