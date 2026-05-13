"""Admin API: stats, reindex."""

from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.database import get_db, SessionLocal
from app.db import crud
from app.db.models import Document, Chunk
from app.rag.vector_store import get_store, delete_chunks
from app.rag.ingest import process_document
from app.config import FILES_DIR

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    stats = crud.get_document_stats(db)

    total_size = 0
    if FILES_DIR.exists():
        for f in FILES_DIR.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size

    stats["storage_mb"] = round(total_size / (1024 * 1024), 2)
    stats["vector_count"] = get_store().count

    html = f"""
    <div class="stats-grid">
        <div class="stat-card">
            <div class="value">{stats['total_documents']}</div>
            <div class="label">文档总数</div>
        </div>
        <div class="stat-card">
            <div class="value">{stats['ready_documents']}</div>
            <div class="label">已就绪</div>
        </div>
        <div class="stat-card">
            <div class="value">{stats['total_chunks']}</div>
            <div class="label">片段总数</div>
        </div>
        <div class="stat-card">
            <div class="value">{stats['vector_count']}</div>
            <div class="label">向量数</div>
        </div>
        <div class="stat-card">
            <div class="value">{stats['storage_mb']} MB</div>
            <div class="label">存储空间</div>
        </div>
    </div>
    """
    return HTMLResponse(html)


@router.post("/reindex")
async def reindex(background_tasks: BackgroundTasks):
    """Delete all vectors and re-process all documents asynchronously."""
    db = SessionLocal()
    try:
        store = get_store()
        all_ids = list(store._id_to_faiss.keys())
        if all_ids:
            delete_chunks(all_ids)

        docs = db.query(Document).all()
        for doc in docs:
            doc.status = "uploaded"
            doc.chunk_count = 0
            db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        db.commit()

        # Process documents in background
        for doc in docs:
            background_tasks.add_task(process_document, doc_id=doc.id)

        return f"<span style='color:green'>已触发 {len(docs)} 个文档的重建，后台处理中...</span>"
    finally:
        db.close()
