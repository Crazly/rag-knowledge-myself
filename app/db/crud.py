from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models import Document, Chunk, gen_uuid


def create_document(db: Session, filename: str, file_path: str,
                    file_size: int, file_hash: str, file_type: str) -> Document:
    doc = Document(
        filename=filename,
        file_path=file_path,
        file_size=file_size,
        file_hash=file_hash,
        file_type=file_type,
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: Session, doc_id: str) -> Document | None:
    return db.query(Document).filter(Document.id == doc_id).first()


def list_documents(db: Session, status: str | None = None,
                   offset: int = 0, limit: int = 50):
    q = db.query(Document)
    if status:
        q = q.filter(Document.status == status)
    total = q.count()
    docs = q.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
    return docs, total


def update_document_status(db: Session, doc_id: str, status: str,
                           chunk_count: int = 0, error_message: str | None = None):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc:
        doc.status = status
        doc.updated_at = datetime.utcnow()
        if chunk_count:
            doc.chunk_count = chunk_count
        if error_message:
            doc.error_message = error_message
        db.commit()


def delete_document(db: Session, doc_id: str):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc:
        db.delete(doc)
        db.commit()


def create_chunk(db: Session, document_id: str, chunk_index: int,
                 content: str, token_count: int, page_number: int | None = None) -> Chunk:
    chunk = Chunk(
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        token_count=token_count,
        page_number=page_number,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


def create_chunks_batch(db: Session, chunk_data: list[dict]) -> list[Chunk]:
    """Batch insert chunks. Each dict: document_id, chunk_index, content, token_count, page_number."""
    chunks = [Chunk(**data) for data in chunk_data]
    db.add_all(chunks)
    db.commit()
    return chunks


def delete_chunks_by_document(db: Session, document_id: str):
    db.query(Chunk).filter(Chunk.document_id == document_id).delete()
    db.commit()


def get_document_stats(db: Session) -> dict:
    doc_count = db.query(Document).count()
    ready_count = db.query(Document).filter(Document.status == "ready").count()
    chunk_count = db.query(Chunk).count()
    return {
        "total_documents": doc_count,
        "ready_documents": ready_count,
        "total_chunks": chunk_count,
    }
