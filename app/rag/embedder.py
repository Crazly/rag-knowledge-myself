"""Embedding service using SiliconFlow BGE-M3 API."""

import httpx

from app.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, EMBEDDING_MODEL


class EmbeddingError(Exception):
    pass


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Get embeddings for multiple texts via SiliconFlow API.

    Returns a list of embedding vectors (each 1024-dim).

    Raises EmbeddingError if API key is not set or the API call fails.
    """
    if not SILICONFLOW_API_KEY:
        raise EmbeddingError(
            "SILICONFLOW_API_KEY not set. Set it via environment variable or .env file."
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SILICONFLOW_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": texts,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        # Sort by index to maintain order
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]


async def embed_single(text: str) -> list[float]:
    """Get embedding for a single text."""
    embeddings = await embed_texts([text])
    return embeddings[0]
