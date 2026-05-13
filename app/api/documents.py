"""Document management API routes."""
import os
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import crud
from app.db.models import Document
from app.rag.ingest import process_document
from app.utils.file_handler import save_uploaded_file, delete_document_files
from app.utils.hash_utils import compute_file_hash
from app.config import FILES_DIR

router = APIRouter(prefix="/documents", tags=["documents"])

EXT_TO_TYPE = {
    ".pdf": "pdf",
    ".md": "markdown",
    ".txt": "markdown",
    ".docx": "word",
    ".xlsx": "excel",
}


def _get_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    file_type = EXT_TO_TYPE.get(ext)
    if file_type is None:
        raise HTTPException(400, f"Unsupported file type: {ext}")
    return file_type


@router.get("", response_class=HTMLResponse)
def list_documents_html(status: str | None = None, db: Session = Depends(get_db)):
    docs, _ = crud.list_documents(db, status=status, limit=100)
    rows = []
    for doc in docs:
        rows.append(f"""
        <tr>
            <td>{doc.filename}</td>
            <td>{doc.file_type}</td>
            <td><span class="status status-{doc.status}">{doc.status}</span></td>
            <td>{doc.chunk_count}</td>
            <td>{doc.created_at.strftime("%Y-%m-%d %H:%M") if doc.created_at else ""}</td>
            <td><button hx-delete="/api/documents/{doc.id}" hx-target="closest tr" hx-swap="outerHTML">删除</button></td>
        </tr>
        """)
    return f"""
    <table>
        <tr><th>文件名</th><th>类型</th><th>状态</th><th>片段数</th><th>上传时间</th><th>操作</th></tr>
        {''.join(rows) if rows else '<tr><td colspan="6">暂无文档</td></tr>'}
    </table>
    """


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(400, "No file provided")

    file_type = _get_file_type(file.filename)
    if file_type not in ("pdf", "markdown", "excel", "word", "web"):
        raise HTTPException(400, f"Unsupported file type: {file_type}. Supported: pdf, md, txt, xlsx, docx, html")

    # Create document record
    doc = crud.create_document(
        db,
        filename=file.filename,
        file_path="",  # Will be updated after save
        file_size=0,
        file_hash="",
        file_type=file_type,
    )

    # Save file
    relative_path = save_uploaded_file(file, doc.id)
    file_full_path = FILES_DIR.parent / relative_path
    file_hash = compute_file_hash(str(file_full_path))

    # Update document with actual file info
    doc.file_path = relative_path
    doc.file_size = os.path.getsize(file_full_path)
    doc.file_hash = file_hash
    db.commit()

    # Trigger async processing (creates its own DB session)
    background_tasks.add_task(process_document, doc_id=doc.id)

    return {"id": doc.id, "filename": doc.filename, "status": doc.status}


@router.get("/{doc_id}")
def get_document(doc_id: str, db: Session = Depends(get_db)):
    doc = crud.get_document(db, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return {
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "error_message": doc.error_message,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.delete("/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    doc = crud.get_document(db, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    # Remove vectors
    from app.rag.vector_store import delete_chunks
    chunk_ids = [c.id for c in doc.chunks]
    if chunk_ids:
        delete_chunks(chunk_ids)

    # Remove files
    delete_document_files(doc_id)

    # Remove database records
    crud.delete_document(db, doc_id)

    return ""
