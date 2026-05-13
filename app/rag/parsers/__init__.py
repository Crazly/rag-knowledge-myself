"""Unified parser interface. Routes to specific parsers by file type."""

from app.rag.parsers.pdf import parse_pdf
from app.rag.parsers.markdown import parse_markdown
from app.rag.parsers.excel import parse_excel
from app.rag.parsers.word import parse_word
from app.rag.parsers.web import parse_web

PARSERS = {
    "pdf": parse_pdf,
    "markdown": parse_markdown,
    "md": parse_markdown,
    "txt": parse_markdown,
    "excel": parse_excel,
    "xlsx": parse_excel,
    "word": parse_word,
    "docx": parse_word,
    "web": parse_web,
    "html": parse_web,
}


def parse_document(file_path: str, file_type: str) -> list[dict]:
    """Parse a document by file type.

    Returns:
        List of dicts, each with keys: text, page_number, metadata.
    """
    parser = PARSERS.get(file_type)
    if parser is None:
        raise ValueError(f"Unsupported file type: {file_type}")
    return parser(file_path)


def get_supported_types() -> list[str]:
    return list(PARSERS.keys())
