"""Retriever: FAISS vector search + BGE-Reranker re-ranking."""

import logging

import httpx

from app.config import (
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE_URL,
    RERANKER_MODEL,
    RETRIEVAL_TOP_K,
    RERANK_TOP_K,
)
from app.rag.embedder import embed_single, EmbeddingError
from app.rag.vector_store import query as vector_query
from app.db.database import SessionLocal
from app.db.models import Chunk

logger = logging.getLogger(__name__)


class RetrieveError(Exception):
    pass


async def retrieve(question: str, top_k: int = 5) -> list[dict]:
    """Full retrieval pipeline: embed → FAISS query → rerank.

    Returns list of {chunk_id, text, document_name, page_number, score}.
    """
    # 1. Embed question
    query_embedding = await embed_single(question)

    # 2. FAISS vector search (Top-20)
    results = vector_query(query_embedding, top_k=RETRIEVAL_TOP_K)
    if not results:
        return []

    chunk_ids = [r["chunk_id"] for r in results]
    chunk_texts = _get_chunk_texts(chunk_ids)

    # 3. BGE-Reranker re-rank (Top-K)
    reranked = await _rerank(question, chunk_texts, chunk_ids)

    # Filter by minimum relevance score
    return [r for r in reranked if r["score"] >= 0.1][:top_k]


def _get_chunk_texts(chunk_ids: list[str]) -> dict[str, str]:
    """Get chunk texts from SQLite. Returns {chunk_id: text}."""
    db = SessionLocal()
    try:
        chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
        return {c.id: c.content for c in chunks}
    finally:
        db.close()


async def _rerank(question: str, chunk_texts: dict[str, str],
                  chunk_ids: list[str]) -> list[dict]:
    """Call BGE-Reranker API to re-rank chunks by relevance to question."""
    if not SILICONFLOW_API_KEY:
        raise RetrieveError("SILICONFLOW_API_KEY not set")

    # Build (id, text) pairs in original order
    pairs = [(cid, chunk_texts.get(cid, "")) for cid in chunk_ids]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SILICONFLOW_BASE_URL}/rerank",
            headers={
                "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": RERANKER_MODEL,
                "query": question,
                "documents": [text for _, text in pairs],
                "top_n": RERANK_TOP_K,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

    # Build results with metadata
    results = []
    db = SessionLocal()
    try:
        for item in data.get("results", []):
            idx = item["index"]
            chunk_id = pairs[idx][0]
            chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
            if chunk and chunk.document:
                results.append({
                    "chunk_id": chunk_id,
                    "text": chunk.content,
                    "document_name": chunk.document.filename,
                    "page_number": chunk.page_number,
                    "score": item.get("relevance_score", 0),
                })
    finally:
        db.close()

    return results
