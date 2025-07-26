# backend/generate_topics.py
import re
import argparse
import json

def extract_title_from_line(line, max_words=7):
    # Remove speaker prefix (e.g., "MR. SMITH:")
    line = re.sub(r"^(MR|MS|MRS)\.?\s+\w+:?\s*", "", line, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^\w\s]", '', line)  # Remove punctuation
    words = cleaned.strip().split()
    return " ".join(words[:max_words]) if words else "Untitled Topic"

def mock_topic_detection(transcript_text):
    lines = transcript_text.strip().split("\n")
    topics = []

    for i, line in enumerate(lines):
        topic_text = line.strip()

        # Filter 1: Must contain at least one letter (skip pure numbers/symbols like "Line 1 · Page 1")
        if not re.search(r"[a-zA-Z]", topic_text):
            continue

        # Filter 2: Must not look like metadata ("Page", "Line", or just digits)
        if re.search(r"\b(Page|Line)\b", topic_text, re.IGNORECASE):
            continue
        if re.fullmatch(r"[0-9 ·]+", topic_text):
            continue

        # Filter 3: Should ideally start with speaker names (relaxed to include common patterns)
        if not re.match(r"^(MR|MS|MRS|THE WITNESS|THE COURT|BY MR|BY MS)", topic_text.upper()):
            continue

        # Passed all filters — add to topics
        title = extract_title_from_line(topic_text, max_words=7)

        topics.append({
            "topic": title,
            "page": (i // 30) + 1,
            "line": i + 1,
            "text": topic_text
        })

    return topics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate topics.json from raw transcript")
    parser.add_argument('--in', dest='input_path', type=str, required=True, help="Path to transcript.txt")
    parser.add_argument('--out', dest='output_path', type=str, default="output/topics.json", help="Path to save topics.json")

    args = parser.parse_args()

    with open(args.input_path, "r", encoding="utf-8") as f:
        transcript_text = f.read()

    topics = mock_topic_detection(transcript_text)

    with open(args.output_path, "w", encoding="utf-8") as f:
        json.dump(topics, f, indent=2)
