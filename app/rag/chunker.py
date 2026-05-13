"""Text chunking using semantic splitting."""

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import Document as LlamaDocument

from app.config import CHUNK_SIZE, CHUNK_OVERLAP

_splitter = SentenceSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)


def chunk_text(text: str) -> list[str]:
    """Split text into semantic chunks. Returns list of chunk strings."""
    nodes = _splitter.get_nodes_from_documents([LlamaDocument(text=text)])
    return [node.get_content() for node in nodes if node.get_content().strip()]


def estimate_tokens(text: str) -> int:
    """Rough token count estimation (Chinese characters + English words)."""
    import re
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    return chinese_chars + english_words
