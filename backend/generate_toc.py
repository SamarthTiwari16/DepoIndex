# backend/generate_toc.py

import json
import argparse
from docx import Document


def load_topics(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            print(f"📂 Loaded topics from {json_path}")
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading JSON file: {e}")
        return []


def filter_and_sort_topics(topics):
    valid_topics = []
    for i, topic in enumerate(topics):
        if not isinstance(topic, dict):
            print(f"⚠️ Skipping: Item at index {i} is not a dictionary: {topic}")
            continue
        if 'page' not in topic or 'line' not in topic:
            print(f"⚠️ Skipping: Missing 'page' or 'line' in topic at index {i}: {topic}")
            continue
        valid_topics.append(topic)

    try:
        valid_topics.sort(key=lambda x: (x['page'], x['line']))
    except (KeyError, TypeError) as e:
        print(f"❌ Error during sorting: {e}")
        return []

    return valid_topics


def save_markdown(topics, output_path):
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# 🧾 Deposition Topic Table of Contents\n\n")
            for item in topics:
                line = f"- **{item.get('topic', 'Unknown Topic')}** · Page {item.get('page', 'N/A')} · Line {item.get('line', 'N/A')}\n"
                f.write(line)
        print(f"✅ Markdown TOC saved at {output_path}")
    except Exception as e:
        print(f"❌ Error saving markdown: {e}")


def save_docx(topics, output_path):
    try:
        doc = Document()
        doc.add_heading('Deposition Topic Table of Contents', level=1)
        for item in topics:
            line = f"{item.get('topic', 'Unknown Topic')} · Page {item.get('page', 'N/A')} · Line {item.get('line', 'N/A')}"
            doc.add_paragraph(line)
        doc.save(output_path)
        print(f"✅ DOCX TOC saved at {output_path}")
    except Exception as e:
        print(f"❌ Error saving DOCX: {e}")


def generate_toc(json_input_path, markdown_path, docx_path):
    topics = load_topics(json_input_path)
    sorted_topics = filter_and_sort_topics(topics)

    if not sorted_topics:
        print("❌ No valid topics found to generate TOC.")
        return False

    save_markdown(sorted_topics, markdown_path)
    save_docx(sorted_topics, docx_path)
    return True


def main():
    parser = argparse.ArgumentParser(description="Export TOC and annotated transcript from topics.json")
    parser.add_argument('--in', dest='input_json', type=str, default="output/topics.json", help="Path to the topics.json file")
    parser.add_argument('--out-md', dest='markdown_path', type=str, default='output/toc.md', help="Output markdown file path")
    parser.add_argument('--out-docx', dest='docx_path', type=str, default='output/toc.docx', help="Output docx file path")

    args = parser.parse_args()

    # Debugging print
    print(f"\n📁 Using topics JSON: {args.input_json}")
    print(f"📄 Will export: Markdown → {args.markdown_path}, Docx → {args.docx_path}")

    success = generate_toc(args.input_json, args.markdown_path, args.docx_path)

    if success:
        print(f"\n✅ TOC generated:\n→ Markdown: {args.markdown_path}\n→ Docx: {args.docx_path}")
    else:
        print("❌ TOC generation failed. Check if 'topics.json' exists and is generated from the uploaded transcript.")


if __name__ == "__main__":
    main()
