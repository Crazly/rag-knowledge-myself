"""Markdown and plain text parser."""


def parse_markdown(file_path: str) -> list[dict]:
    """Parse a markdown or text file. Returns one page-like item."""
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        return []

    return [{
        "text": text,
        "page_number": None,
        "metadata": {
            "file_type": "markdown",
        },
    }]
