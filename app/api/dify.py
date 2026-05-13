"""Dify External Knowledge API compatible endpoint.

Dify 外部知识库 API 规范：
  POST /api/dify/retrieve
  Request:  {"query": "...", "knowledge_id": "..."}
  Response: {"records": [{"content": "...", "score": 0.9, "title": "...", ...}]}
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.rag.retriever import retrieve, RetrieveError
from app.rag.embedder import EmbeddingError

router = APIRouter(prefix="/dify", tags=["dify"])


class DifyRetrieveRequest(BaseModel):
    query: str
    knowledge_id: str = ""


class DifyRetrieveResponse(BaseModel):
    records: list[dict]


@router.post("/retrieve")
async def dify_retrieve(request: DifyRetrieveRequest):
    """Dify 外部知识库检索接口。

    直接返回 Dify 要求的 records 格式，无需额外转换。
    """
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty")

    try:
        sources = await retrieve(request.query, top_k=5)
    except EmbeddingError as e:
        raise HTTPException(500, f"Embedding error: {e}")
    except RetrieveError as e:
        raise HTTPException(500, f"Retrieval error: {e}")

    records = []
    for s in sources:
        records.append({
            "content": s["text"],
            "score": s["score"],
            "title": s.get("document_name", ""),
            "document_name": s.get("document_name", ""),
            "chunk_id": s.get("chunk_id", ""),
            "page_number": s.get("page_number"),
            "source": f"{s.get('document_name', '')}"
                      f"{' (第' + str(s['page_number']) + '页)' if s.get('page_number') else ''}",
        })

    return {"records": records}


@router.get("/health")
async def dify_health():
    """Dify 知识库健康检查。"""
    from app.db.database import SessionLocal
    from app.db import crud
    db = SessionLocal()
    try:
        stats = crud.get_document_stats(db)
        return {
            "status": "ok",
            "documents": stats["total_documents"],
            "chunks": stats["total_chunks"],
        }
    finally:
        db.close()
