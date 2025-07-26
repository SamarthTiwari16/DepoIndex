# backend/export_transcript.py

import json
from docx import Document

def export_full_transcript(topics_path, out_md, out_docx):
    with open(topics_path, "r", encoding="utf-8") as f:
        topics = json.load(f)

    # --- MARKDOWN EXPORT ---
    md_lines = ["# Table of Contents\n"]
    for i, topic in enumerate(topics, 1):
        md_lines.append(f"{i}. {topic['topic']} ........................ Page {topic['page']} · Line {topic['line']}")
    md_lines.append("\n---\n")

    for i, topic in enumerate(topics, 1):
        md_lines.append(f"## {i}. {topic['topic']}")
        md_lines.append(f"(Page {topic['page']} · Line {topic['line']})\n")
        md_lines.append(topic['text'])
        md_lines.append("\n")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # --- DOCX EXPORT ---
    doc = Document()
    doc.add_heading("Table of Contents", level=1)
    for i, topic in enumerate(topics, 1):
        doc.add_paragraph(f"{i}. {topic['topic']} ........................ Page {topic['page']} · Line {topic['line']}")

    doc.add_page_break()

    for i, topic in enumerate(topics, 1):
        doc.add_heading(f"{i}. {topic['topic']}", level=2)
        doc.add_paragraph(f"(Page {topic['page']} · Line {topic['line']})")
        doc.add_paragraph(topic['text'])

    doc.save(out_docx)
