import streamlit as st
import sqlite3
import os
from PIL import Image, ImageOps
import io

st.set_page_config(page_title="Ajay Srinivasan Archive", layout="wide")

def auto_rotate_image(image_path):
    """Auto-rotate image based on EXIF or orientation detection"""
    try:
        img = Image.open(image_path)
        # Try to auto-rotate based on EXIF orientation
        img = ImageOps.exif_transpose(img)
        return img
    except Exception as e:
        try:
            return Image.open(image_path)
        except:
            return None

def get_connection():
    conn = sqlite3.connect("archive.db", check_same_thread=False, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

st.sidebar.title("Filter & Research Options")

conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT folder_name FROM articles ORDER BY folder_name")
folders = ["All Eras / Folders"] + [r[0] for r in cursor.fetchall()]
conn.close()
selected_folder = st.sidebar.selectbox("Filter by Era / Folder:", folders)

sort_option = st.sidebar.radio("Sort Results By:", ["Folder / Era Name", "File Name"])

user_query = st.text_input("🔍 Search Archive (e.g., 'ICICI', 'bourses', 'prudential'):")

sql = "SELECT file_name, folder_name, file_path, parsed_text FROM articles WHERE 1=1"
params = []

if selected_folder != "All Eras / Folders":
    sql += " AND folder_name = ?"
    params.append(selected_folder)

if user_query.strip():
    words = [w.strip() for w in user_query.lower().split() if w.strip()]
    if words:
        sql += " AND (" + " OR ".join(["parsed_text LIKE ?" for _ in words]) + ")"
        for w in words:
            params.append(f"%{w}%")

if sort_option == "Folder / Era Name":
    sql += " ORDER BY folder_name ASC, file_name ASC"
else:
    sql += " ORDER BY file_name ASC"

conn = get_connection()
cursor = conn.cursor()
cursor.execute(sql, params)
results = cursor.fetchall()
conn.close()

st.title("📰 Ajay Srinivasan Digital Archive")
st.write(f"Showing **{len(results)}** article(s)")

for idx, (file_name, folder_name, file_path, parsed_text) in enumerate(results):
    st.divider()
    st.subheader(f"📁 Era/Folder: {folder_name} | 📄 File: {file_name}")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        exact_path = os.path.normpath(file_path).replace("\\", "/")
        fallback_path = f"images/{folder_name}/{file_name}"

        img = None
        if os.path.exists(exact_path):
            img = auto_rotate_image(exact_path)
        elif os.path.exists(fallback_path):
            img = auto_rotate_image(fallback_path)

        if img:
            st.image(img, use_container_width=True, caption=f"Scan: {file_name}")
        else:
            st.info(f"📁 Image file: {file_name}")

    with col2:
        st.markdown("### Extracted Text (For Manuscript Reference):")
        st.text_area(
            label="OCR Text Transcript",
            value=parsed_text if parsed_text else "No text extracted.",
            height=450,
            key=f"txt_{idx}"
        )
        st.download_button(
            label="💾 Export Transcript (.txt)",
            data=parsed_text if parsed_text else "",
            file_name=f"{file_name}_transcript.txt",
            mime="text/plain",
            key=f"dl_{idx}"
        )