"""LLM response cache using SQLite. Caches (question, answer, sources) so
identical questions don't incur API costs."""

import hashlib
import json

from app.db.database import SessionLocal
from app.db.models import QACache


def _hash(question: str) -> str:
    return hashlib.md5(question.strip().encode("utf-8")).hexdigest()


def get_cached(question: str) -> dict | None:
    """Check if a question has a cached answer. Returns {answer, sources} or None."""
    db = SessionLocal()
    try:
        key = _hash(question)
        cached = db.query(QACache).filter(QACache.id == key).first()
        if cached:
            return {
                "answer": cached.answer,
                "sources": json.loads(cached.sources) if cached.sources else [],
            }
        return None
    finally:
        db.close()


def set_cache(question: str, answer: str, sources: list[dict]):
    """Cache an answer for a question."""
    db = SessionLocal()
    try:
        key = _hash(question)
        existing = db.query(QACache).filter(QACache.id == key).first()
        if existing:
            existing.answer = answer
            existing.sources = json.dumps(sources)
        else:
            db.add(QACache(
                id=key,
                question=question,
                answer=answer,
                sources=json.dumps(sources),
            ))
        db.commit()
    finally:
        db.close()
