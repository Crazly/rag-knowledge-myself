"""APScheduler jobs for auto-update (Phase 1 & 2 autonomy)."""

import logging
import os
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import FILES_DIR
from app.db.database import SessionLocal
from app.db import crud
from app.rag.ingest import process_document
from app.utils.hash_utils import compute_file_hash

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def _scan_files():
    """Scan data/files/ directory, discovering:
    1. New files not in the database → trigger processing
    2. Modified files (hash changed) → delete old + re-process
    """
    db = SessionLocal()
    try:
        known_docs = {d.id: d for d in crud.list_documents(db, limit=10000)[0]}

        for doc_dir in FILES_DIR.iterdir():
            if not doc_dir.is_dir():
                continue
            doc_id = doc_dir.name

            for file_path in doc_dir.iterdir():
                if file_path.is_file():
                    current_hash = compute_file_hash(str(file_path))
                    existing = known_docs.get(doc_id)

                    if existing is None:
                        # New file — register and queue processing
                        ext = file_path.suffix.lower()
                        type_map = {".pdf": "pdf", ".md": "markdown", ".txt": "markdown",
                                    ".xlsx": "excel", ".docx": "word", ".html": "web"}
                        file_type = type_map.get(ext, "markdown")

                        doc = crud.create_document(
                            db,
                            filename=file_path.name,
                            file_path=str(file_path.relative_to(FILES_DIR.parent)),
                            file_size=os.path.getsize(file_path),
                            file_hash=current_hash,
                            file_type=file_type,
                        )
                        logger.info(f"Discovered new file: {file_path.name}")
                        # Schedule async processing
                        import asyncio
                        asyncio.ensure_future(process_document(doc.id))

                    elif existing.file_hash and existing.file_hash != current_hash:
                        # Modified file — re-process
                        logger.info(f"Detected change: {existing.filename}")
                        from app.rag.vector_store import delete_chunks
                        chunk_ids = [c.id for c in existing.chunks]
                        if chunk_ids:
                            delete_chunks(chunk_ids)
                        crud.delete_chunks_by_document(db, existing.id)
                        existing.file_hash = current_hash
                        existing.file_size = os.path.getsize(file_path)
                        db.commit()
                        import asyncio
                        asyncio.ensure_future(process_document(existing.id))
    except Exception:
        logger.exception("File scan failed")
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        _scan_files,
        "interval",
        minutes=5,
        id="scan_files",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: scanning every 5 minutes")
