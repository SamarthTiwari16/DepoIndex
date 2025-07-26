from utils import parse_transcript, chunk_transcript
from model import call_gpt_topic_detector, build_topic_clusters
from dotenv import load_dotenv
import json
import os
import subprocess

# Load .env variables
load_dotenv()

# Load the transcript
lines = parse_transcript("data/sample_transcript.txt")

# Chunk the transcript
chunks = chunk_transcript(lines, chunk_size=3)  # adjust chunk_size as needed

# Step 1: Build topic clusters
if len(chunks) >= 2:
    actual_clusters = min(5, len(chunks))
    chunks = build_topic_clusters(chunks, n_clusters=actual_clusters)
else:
    print("❗ Not enough chunks to perform clustering.")
    chunks = []

# Step 2: Collect cluster-assigned topics
topics = []
for i, chunk in enumerate(chunks):
    topics.append({
        "chunk_index": i + 1,
        "topic": chunk["topic_name"],
        "page": chunk["page"],
        "line": chunk["line"],
        "text": chunk["text"]
    })

# Step 3: Display topics
print("\n📘 Extracted Topics:\n")
for t in topics:
    print(f"Chunk {t['chunk_index']}: {t['topic']} (Page {t['page']} · Line {t['line']})")

# Step 4: Save topics to file
os.makedirs("output", exist_ok=True)
with open("output/topics.json", "w", encoding="utf-8") as f:
    json.dump(topics, f, indent=2)
print("\n✅ Topics saved to 'output/topics.json'")

# Step 5: Generate TOC
subprocess.run([
    "python", "backend/export_transcript.py",
    "--topics", "output/topics.json",
    "--out-md", "output/toc.md",
    "--out-docx", "output/toc.docx"
])

# Step 6: Generate Annotated Transcript
subprocess.run([
    "python", "backend/annotated_transcript.py",
    "--topics", "output/topics.json",
    "--out-md", "output/annotated_transcript.md",
    "--out-docx", "output/annotated_transcript.docx"
])
