import re
import os

def parse_transcript(file_path):
    """
    Parses the transcript file and returns a list of dictionaries with page, line, and text info.
    Expected format:
      Page 1
      Line 1: This is the text.
      Line 2: More text.
      Page 2
      ...
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Transcript file not found at: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    parsed_lines = []
    current_page = None

    for raw_line in lines:
        line = raw_line.strip()

        # Detect page number
        page_match = re.match(r'^Page\s+(\d+)', line, re.IGNORECASE)
        if page_match:
            current_page = int(page_match.group(1))
            continue

        # Detect line with transcript text
        line_match = re.match(r'^Line\s+(\d+):\s+(.*)', line, re.IGNORECASE)
        if line_match and current_page is not None:
            line_num = int(line_match.group(1))
            text = line_match.group(2).strip()
            if text:
                parsed_lines.append({
                    "page": current_page,
                    "line": line_num,
                    "text": text
                })

    if not parsed_lines:
        raise ValueError("Transcript file is empty or contains no valid lines.")

    return parsed_lines


def chunk_transcript(parsed_lines, chunk_size=50):
    """
    Chunks parsed transcript lines into groups of `chunk_size` lines.
    Each chunk retains the page and line number of its first line.
    """
    if not parsed_lines:
        return []

    chunks = []
    for i in range(0, len(parsed_lines), chunk_size):
        chunk_lines = parsed_lines[i:i + chunk_size]
        text = " ".join([line["text"] for line in chunk_lines])
        first_line = chunk_lines[0]

        chunks.append({
            "text": text,
            "page": first_line["page"],
            "line": first_line["line"]
        })

    return chunks
