import streamlit as st
import sqlite3
import os

st.set_page_config(layout="wide", page_title="Ajay Srinivasan — Book Research Repository")
st.title("📚 Ajay Srinivasan Archive — Book Research Repository")

DB_NAME = "archive.db"

if not os.path.exists(DB_NAME):
    st.error("Database 'archive.db' not found. Please run indexer.py first.")
    st.stop()

# Fetch distinct folder names for era filtering
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT folder_name FROM articles ORDER BY folder_name")
available_folders = [row[0] for row in cursor.fetchall()]

# Sidebar Controls
st.sidebar.header("🔍 Filter & Research Options")

selected_folder = st.sidebar.selectbox(
    "Filter by Era / Folder:",
    ["All Eras / Folders"] + available_folders
)

sort_order = st.sidebar.radio(
    "Sort Results By:",
    ["Relevance Score", "Folder / Era Name"]
)

# Search Input
user_query = st.text_input("💬 Search topics, keywords, or questions (e.g., 'FII limit', 'Sensex', 'Budget', 'Threadneedle'):")

# SQL Construction
sql = "SELECT file_name, folder_name, file_path, parsed_text FROM articles WHERE 1=1"
params = []

if selected_folder != "All Eras / Folders":
    sql += " AND folder_name = ?"
    params.append(selected_folder)

# Natural Language Search Logic
stop_words = {'what', 'were', 'was', 'about', 'the', 'how', 'did', 'where', 'when', 'who', 'which', 'and', 'for', 'with', 'in', 'on', 'is', 'a', 'of', 'to'}
query_words = []

if user_query.strip():
    query_words = [word.strip() for word in user_query.lower().split() if word.strip() not in stop_words and len(word.strip()) > 2]
    if query_words:
        conditions = " AND (" + " OR ".join(["parsed_text LIKE ?" for _ in query_words]) + ")"
        sql += conditions
        for word in query_words:
            params.append(f"%{word}%")

cursor.execute(sql, params)
results = cursor.fetchall()
conn.close()

# Sorting Results
if query_words and sort_order == "Relevance Score":
    def score_article(art):
        text = art[3].lower()
        return sum(text.count(w) for w in query_words)
    results = sorted(results, key=score_article, reverse=True)
elif sort_order == "Folder / Era Name":
    results = sorted(results, key=lambda x: x[1])

st.markdown(f"### Matching Clippings ({len(results)} found)")

if not results:
    st.info("No matching clippings found. Try adjusting your query or folder filter.")

# Display Results
for idx, (file_name, folder_name, file_path, parsed_text) in enumerate(results):
    st.markdown("---")
    st.subheader(f"📁 Era/Folder: **{folder_name}** | 📄 File: `{file_name}`")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Handle both absolute paths (local) and relative paths (production)
        image_to_display = file_path
        if not os.path.exists(image_to_display):
            # Try relative path for production deployment
            # Search for the file in images folder recursively
            for root, dirs, files in os.walk("images"):
                if file_name in files:
                    image_to_display = os.path.join(root, file_name)
                    break

        if os.path.exists(image_to_display):
            st.image(image_to_display, use_container_width=True, caption=f"Original Scan: {file_name}")
        else:
            st.error(f"Image file missing: {file_name}")

    with col2:
        st.markdown("**Extracted Text (For Manuscript Reference):**")
        st.text_area("OCR Text Transcript", parsed_text, height=420, key=f"text_{idx}")
        
        # Download button to export text straight to manuscript research folder
        st.download_button(
            label="💾 Export Transcript (.txt)",
            data=f"Source: {file_name}\nFolder: {folder_name}\n\n---\n\n{parsed_text}",
            file_name=f"{os.path.splitext(file_name)[0]}_transcript.txt",
            mime="text/plain",
            key=f"dl_{idx}"
        )