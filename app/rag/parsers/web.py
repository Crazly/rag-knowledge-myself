"""Web page parser using trafilatura."""

import trafilatura


def parse_web(url_or_path: str) -> list[dict]:
    """Parse web content, either from a URL or a saved HTML file."""
    # If it looks like a URL, download and parse
    if url_or_path.startswith(("http://", "https://")):
        downloaded = trafilatura.fetch_url(url_or_path)
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    else:
        # Treat as a local HTML file
        with open(url_or_path, "r", encoding="utf-8") as f:
            html = f.read()
        text = trafilatura.extract(html, include_comments=False, include_tables=False)

    if not text or not text.strip():
        return []

    return [{
        "text": text.strip(),
        "page_number": None,
        "metadata": {"file_type": "web"},
    }]
