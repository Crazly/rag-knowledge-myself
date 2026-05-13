"""PDF parser using PyMuPDF."""
from pathlib import Path
import fitz  # PyMuPDF


def parse_pdf(file_path: str) -> list[dict]:
    """Parse a PDF file, returning list of {text, page_number, metadata}."""
    results = []
    doc = fitz.open(file_path)
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if text:
            results.append({
                "text": text,
                "page_number": page_num,
                "metadata": {
                    "total_pages": len(doc),
                    "file_type": "pdf",
                },
            })
    doc.close()
    return results
