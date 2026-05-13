"""Word document parser using python-docx."""

from docx import Document as DocxDocument


def parse_word(file_path: str) -> list[dict]:
    """Parse a Word (.docx) file, extracting paragraphs grouped by page-like chunks."""
    doc = DocxDocument(file_path)

    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    if not paragraphs:
        return []

    # Group paragraphs into reasonable chunks (every ~20 paragraphs = one "page")
    results = []
    chunk_size = 20
    for i in range(0, len(paragraphs), chunk_size):
        chunk_text = "\n".join(paragraphs[i:i + chunk_size])
        results.append({
            "text": chunk_text,
            "page_number": i // chunk_size + 1,
            "metadata": {"file_type": "word"},
        })

    return results
