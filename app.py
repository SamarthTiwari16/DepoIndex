import streamlit as st
import os
import subprocess

st.title("🧾 Deposition Transcript Analyzer")

st.markdown("### 📤 Upload or Paste Transcript")

uploaded_file = st.file_uploader("Upload Transcript File", type=["txt", "pdf", "docx"])
manual_text = st.text_area("Or paste transcript text below", height=300)

# Step 1: Read user input
input_text = ""

if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1]
    
    if file_ext == "txt":
        input_text = uploaded_file.read().decode("utf-8")
    elif file_ext == "pdf":
        from PyPDF2 import PdfReader
        reader = PdfReader(uploaded_file)
        input_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif file_ext == "docx":
        from docx import Document
        doc = Document(uploaded_file)
        input_text = "\n".join(p.text for p in doc.paragraphs)

elif manual_text:
    input_text = manual_text.strip()

# Step 2: Save input to the correct file
if input_text:
    os.makedirs("data", exist_ok=True)
    with open("data/sample_transcript.txt", "w", encoding="utf-8") as f:
        f.write(input_text)
    st.success("✅ Transcript saved successfully!")

# Optional Debug: Show saved text
# st.markdown("#### 🔍 Preview Input Text")
# st.code(input_text[:1000], language="text")

# Step 3: Generate outputs on button click
if input_text:
    if st.button("🚀 Generate TOC and Annotations"):

        try:
            # TOC (JSON)
            subprocess.run([
                "python", "backend/main.py"
            ], check=True)

            # TOC Markdown & DOCX
            subprocess.run([
                "python", "backend/generate_toc_export.py",
                "--in", "output/topics.json",
                "--out-md", "output/toc.md",
                "--out-docx", "output/toc.docx"
            ])

            # Annotated transcript Markdown & DOCX
            subprocess.run([
                "python", "backend/annotated_transcript.py"
            ], check=True)

            st.success("✅ Files generated successfully! Scroll down to download.")
        except subprocess.CalledProcessError as e:
            st.error("❌ Error while running backend scripts.")
            st.code(str(e))

# Step 4: Download buttons for output files
st.markdown("### 📥 Download Outputs")

def show_download(label, path, file_name, binary=False):
    if os.path.exists(path):
        mode = "rb" if binary else "r"
        with open(path, mode, encoding=None if binary else "utf-8") as f:
            st.download_button(label, f, file_name=file_name)

show_download("📘 Download TOC (Markdown)", "output/toc.md", "toc.md")
show_download("📘 Download TOC (DOCX)", "output/toc.docx", "toc.docx", binary=True)
show_download("📝 Download Annotated Transcript (Markdown)", "output/annotated_transcript.md", "annotated_transcript.md")
show_download("📝 Download Annotated Transcript (DOCX)", "output/annotated_transcript.docx", "annotated_transcript.docx", binary=True)
