import streamlit as st
import sqlite3
import os
from PIL import Image, ImageOps
import io

st.set_page_config(page_title="Ajay Srinivasan Archive", layout="wide")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, "archive.db")
IMAGE_DIR = os.path.join(PROJECT_DIR, "images")
SCAN_MIRROR = "[SCANS]_ Ajay Srinivisan_ 14th August"


def resolve_scan_path(file_path):
    """Resolve the stored path or its matching path in the archive mirror."""
    exact_path = os.path.normpath(file_path)
    if not os.path.isabs(exact_path):
        exact_path = os.path.join(PROJECT_DIR, exact_path)
    if os.path.isfile(exact_path):
        return exact_path

    relative_path = os.path.relpath(exact_path, IMAGE_DIR).replace("\\", "/")
    mirror_prefix = f"{SCAN_MIRROR}/"
    if relative_path == ".." or relative_path.startswith(f"..{os.sep}"):
        return None

    if relative_path.casefold().startswith("[scans]_ ajay srinivisan_ 14th august/"):
        alternate_relative = relative_path[len(mirror_prefix):]
    else:
        alternate_relative = f"{mirror_prefix}{relative_path}"

    alternate_path = os.path.join(IMAGE_DIR, *alternate_relative.split("/"))
    return alternate_path if os.path.isfile(alternate_path) else None

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
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
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

sql = "SELECT id, file_name, folder_name, file_path, parsed_text FROM articles WHERE 1=1"
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

for article_id, file_name, folder_name, file_path, parsed_text in results:
    st.divider()
    st.subheader(f"📁 Era/Folder: {folder_name} | 📄 File: {file_name}")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        resolved_path = resolve_scan_path(file_path)
        img = auto_rotate_image(resolved_path) if resolved_path else None

        if img:
            st.image(img, use_container_width=True, caption=f"Scan: {file_name}")
        else:
            st.warning(f"Scan not found in the deployed image archive: {file_name}")

    with col2:
        st.markdown("### Extracted Text (For Manuscript Reference):")
        st.text_area(
            label="OCR Text Transcript",
            value=parsed_text if parsed_text else "No text extracted.",
            height=450,
            key=f"txt_{article_id}"
        )
        st.download_button(
            label="💾 Export Transcript (.txt)",
            data=parsed_text if parsed_text else "",
            file_name=f"{file_name}_transcript.txt",
            mime="text/plain",
            key=f"dl_{article_id}"
        )