import sqlite3
from pathlib import Path

# Properly formatted text extracted reading columns left-to-right
corrected_text = """2 THE ASIAN WALL STREET JOURNAL TUESDAY, SEPTEMBER 7, 1993

AMERICA

AMD Shares Fall on Remarks On Cloned Chips

By G. CHRISTIAN HILL
Staff Reporter

SUNNYVALE, California — Advanced Micro Devices' issued confusing admissions that an allegedly "clean-room" clone of Intel Corp.'s best-selling microprocessor actually borrowed heavily from copyrighted Intel software, depressing the company's stock $2 a share, or 6.5%.

AMD stock closed at $29 a share, down $2 Friday in trading on the New York Stock Exchange.

In a prepared statement issued late Thursday, AMD said engineers developing a so-called clean-room version of Intel's 486 chip had been "exposed" to microcode, or embedded software instructions, used in Intel's predecessor 386 chip. The statement added that "some portion of the 386 microcode was probably incorporated" in AMD's "clean" microprocessor, called the Am486SX. In a clean-room clone, engineers supposedly start from scratch in their efforts to copy a chip, receiving no patented or copyrighted material.

AMD announced the Am486SX on July 5, declaring it represented an "independence day" from Intel. A month earlier, a California court of appeals had ruled that AMD wasn't entitled to use Intel's 386 microcode under a previous technology-sharing agreement. Analysts expressed

New Ways to Lift Economy Are Sought by White House

By DAVID WESSEL
And LUCINDA HARPER
Staff Reporters

WASHINGTON — Faced with an economic recovery more shaky than hoped, several of U.S. President Bill Clinton's top advisers are looking for ways to stimulate the economy without widening the deficit.

Officials from the president's Council of Economic Advisers and the Labor Department are engaged in what council member Alan Blinder calls "internal brainstorming . . . that may or may not lead anywhere." The suggestions range from accelerating federal spending on certain national programs to targeting discretionary programs funds into specific regions such as Southern California and south Florida.

Clinton administration officials hope to assemble a list of proposals in the next month or so, then put forth the best of those to the National Economic Council, which would make recommendations to the president.

The team was put together three months ago to study possible stimulative moves. "We have a recovery under way in the international economy. That's the macroeconomic picture," Labor Secretary Robert Reich said Monday. "But the question we have been asking is: 'What are the microeconomic things we can do?'"

The latest evidence that all isn't well with the U.S. economy came Friday when the Labor Department said that employers cut 50,000 jobs in August, indicating that the labor market is weakening as the summer doldrums set in. That sized that no proposal is certain regarding the possible stimulus plan. "Any administration considers many ideas that it never embraces, and it should be understood that all of this is in the early thinking stages," Mr. Blinder said.

Because of various laws and the nature of government spending, the president's ability to channel spending, particularly from one fiscal year to the next, is very limited, as President George Bush discovered earlier when he tried maneuvers similar to those Mr. Clinton's aides are considering.

Mr. Clinton tried unsuccessfully early in his year to persuade Congress to cut taxes and increase spending temporarily to stimulate the economy, and the administration has no interest in reopening that question. In fact, the White House now is emphasizing its plan to offer Congress a new package of spending cuts in October and is determined to shrink the federal work force.

The administration, however, is planning to spend money to ask Congress to extend a federal jobs program that provides unemployment benefits to workers whose state benefits have run out. Without congressional action, the program will expire early next month. That would cost the government money in terms of lost tax revenues and increased spending. The administration official familiar with the discussions also noted that it is pursuing the expansion of its "empowerment zones" program, which would provide tax breaks and spending for economically distressed regions.
"""

db_path = Path("archive.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Update article ID 1649 with corrected text
cursor.execute("""
    UPDATE articles
    SET parsed_text = ?
    WHERE id = 1649
""", (corrected_text,))

conn.commit()

# Verify the update
cursor.execute("SELECT id, file_name, parsed_text FROM articles WHERE id = 1649")
result = cursor.fetchone()
conn.close()

if result:
    article_id, file_name, text = result
    print(f"✓ Updated article ID {article_id}")
    print(f"  File: {file_name}")
    print(f"  New text length: {len(text)} chars")
    print(f"\nFirst 400 chars of corrected text:")
    print(text[:400])
else:
    print("Failed to update article")
