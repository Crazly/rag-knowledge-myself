"""Document ingestion pipeline: parse → chunk → embed → store."""

import logging

from app.rag.parsers import parse_document
from app.rag.chunker import chunk_text, estimate_tokens
from app.rag.embedder import embed_texts
from app.rag.vector_store import add_chunks
from app.db.database import SessionLocal
from app.db import crud
from app.config import FILES_DIR

logger = logging.getLogger(__name__)


async def process_document(doc_id: str):
    """Full ingestion pipeline for a document. Creates its own DB session."""
    db = SessionLocal()
    try:
        doc = crud.get_document(db, doc_id)
        if not doc:
            logger.error(f"Document {doc_id} not found")
            return

        crud.update_document_status(db, doc_id, "processing")

        # 1. Parse
        file_path = FILES_DIR.parent / doc.file_path
        parsed_pages = parse_document(str(file_path), doc.file_type)
        if not parsed_pages:
            raise ValueError("Document produced no text content")

        # 2. Chunk
        all_chunks = []
        for page in parsed_pages:
            chunks = chunk_text(page["text"])
            for text in chunks:
                all_chunks.append({
                    "text": text,
                    "page_number": page.get("page_number"),
                    "document_id": doc_id,
                })

        # 3. Embed
        texts = [c["text"] for c in all_chunks]
        embeddings = await embed_texts(texts)

        # 4. Store in SQLite
        chunk_records = []
        chunk_data_list = []
        for i, (chunk_data, embedding) in enumerate(zip(all_chunks, embeddings)):
            chunk = crud.create_chunk(
                db,
                document_id=doc_id,
                chunk_index=i,
                content=chunk_data["text"],
                token_count=estimate_tokens(chunk_data["text"]),
                page_number=chunk_data["page_number"],
            )
            chunk_records.append(chunk)

        # 5. Store in ChromaDB
        metadatas = [{
            "document_id": doc_id,
            "filename": doc.filename,
            "page_number": c["page_number"],
            "file_type": doc.file_type,
        } for c in all_chunks]

        add_chunks(
            chunk_ids=[c.id for c in chunk_records],
            embeddings=embeddings,
            texts=texts,
            metadatas=metadatas,
        )

        # 6. Update status to ready
        crud.update_document_status(db, doc_id, "ready", chunk_count=len(chunk_records))
        logger.info(f"Document {doc.filename} processed: {len(chunk_records)} chunks")

    except Exception as e:
        logger.exception(f"Failed to process document {doc_id}")
        crud.update_document_status(db, doc_id, "failed", error_message=str(e))
    finally:
        db.close()
