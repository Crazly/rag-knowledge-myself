#!/usr/bin/env python3
"""Batch import script: import all supported files from a directory into the knowledge base.

Usage:
    python scripts/import.py /path/to/notes
    python scripts/import.py /path/to/notes --recursive
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from app.db.database import SessionLocal, init_db
from app.db import crud
from app.rag.ingest import process_document
from app.utils.hash_utils import compute_file_hash

EXT_TO_TYPE = {
    ".pdf": "pdf",
    ".md": "markdown",
    ".txt": "markdown",
    ".xlsx": "excel",
    ".docx": "word",
    ".html": "web",
    ".htm": "web",
}


async def import_directory(dir_path: str, recursive: bool = False):
    init_db()
    path = Path(dir_path)
    if not path.exists():
        print(f"Error: {dir_path} does not exist")
        return

    pattern = "**/*" if recursive else "*"
    files = []
    for f in path.glob(pattern):
        if f.is_file() and f.suffix.lower() in EXT_TO_TYPE:
            files.append(f)

    if not files:
        print("No supported files found.")
        return

    print(f"Found {len(files)} file(s) to import.\n")

    db = SessionLocal()
    try:
        for i, file_path in enumerate(files, 1):
            ext = file_path.suffix.lower()
            file_type = EXT_TO_TYPE[ext]
            file_hash = compute_file_hash(str(file_path))

            print(f"[{i}/{len(files)}] {file_path.name} ...", end=" ", flush=True)

            try:
                doc = crud.create_document(
                    db,
                    filename=file_path.name,
                    file_path=str(file_path),
                    file_size=os.path.getsize(file_path),
                    file_hash=file_hash,
                    file_type=file_type,
                )
                await process_document(doc.id)
                doc = crud.get_document(db, doc.id)
                print(f"OK ({doc.chunk_count} chunks)")
            except Exception as e:
                print(f"FAILED: {e}")
    finally:
        db.close()

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import documents into knowledge base")
    parser.add_argument("directory", help="Directory containing documents")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recurse into subdirectories")
    args = parser.parse_args()

    asyncio.run(import_directory(args.directory, args.recursive))
