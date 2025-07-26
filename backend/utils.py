import re

def parse_transcript(file_path):
    """
    Parses the transcript file and returns a list of lines with page, line, and text.
    Expected format:
    Page 1
    Line 1: This is the text.
    Line 2: More text.
    Page 2
    ...
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    parsed_lines = []
    current_page = 1

    for line in lines:
        page_match = re.match(r'Page\s+(\d+)', line.strip())
        line_match = re.match(r'Line\s+(\d+):\s+(.*)', line.strip())

        if page_match:
            current_page = int(page_match.group(1))

        elif line_match:
            line_num = int(line_match.group(1))
            text = line_match.group(2).strip()
            parsed_lines.append({
                "page": current_page,
                "line": line_num,
                "text": text
            })

    return parsed_lines


def chunk_transcript(parsed_lines, chunk_size=50):
    """
    Chunks parsed transcript lines into groups of specified size,
    preserving page and line info from the first line in each chunk.
    """
    chunks = []
    for i in range(0, len(parsed_lines), chunk_size):
        chunk_lines = parsed_lines[i:i + chunk_size]
        text = " ".join([line["text"] for line in chunk_lines])
        if chunk_lines:
            page = chunk_lines[0]["page"]
            line_num = chunk_lines[0]["line"]
        else:
            page = 1
            line_num = 1

        chunks.append({
            "text": text,
            "page": page,
            "line": line_num
        })

    return chunks
