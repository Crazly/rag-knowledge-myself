import shutil
import uuid
from pathlib import Path

from app.config import FILES_DIR


def save_uploaded_file(upload_file, document_id: str) -> str:
    """Save uploaded file to data/files/{document_id}/{filename}.
    Returns the relative file path.
    """
    doc_dir = FILES_DIR / document_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    dest = doc_dir / upload_file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(upload_file.file, f)
    return str(dest.relative_to(FILES_DIR.parent))


def delete_document_files(document_id: str):
    """Delete all files for a document."""
    doc_dir = FILES_DIR / document_id
    if doc_dir.exists():
        shutil.rmtree(doc_dir)
