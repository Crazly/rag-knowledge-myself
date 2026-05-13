"""Vector store using FAISS (lighter than ChromaDB, better for 2C2G)."""

import json
import numpy as np
import faiss

from app.config import CHROMA_DIR


def _index_path() -> str:
    return str(CHROMA_DIR / "faiss.index")


def _id_map_path() -> str:
    return str(CHROMA_DIR / "id_map.json")


class VectorStore:
    """FAISS-backed vector store with cosine similarity."""

    def __init__(self):
        self._index: faiss.Index | None = None
        self._id_to_faiss: dict[str, int] = {}  # chunk_id -> faiss internal id
        self._faiss_to_id: dict[int, str] = {}  # faiss internal id -> chunk_id
        self._next_id: int = 0
        self._load()

    def _ensure_index(self, dim: int):
        if self._index is None:
            quantizer = faiss.IndexFlatIP(dim)
            self._index = faiss.IndexIDMap(quantizer)

    def _load(self):
        try:
            self._index = faiss.read_index(_index_path())
            ntotal = self._index.ntotal
            with open(_id_map_path(), "r") as f:
                data = json.load(f)
            self._id_to_faiss = data["id_to_faiss"]
            self._faiss_to_id = {int(k): v for k, v in data["faiss_to_id"].items()}
            self._next_id = data.get("next_id", ntotal)
        except (FileNotFoundError, RuntimeError):
            self._index = None
            self._id_to_faiss = {}
            self._faiss_to_id = {}
            self._next_id = 0

    def _save(self):
        if self._index is not None:
            faiss.write_index(self._index, _index_path())
            with open(_id_map_path(), "w") as f:
                json.dump({
                    "id_to_faiss": self._id_to_faiss,
                    "faiss_to_id": {str(k): v for k, v in self._faiss_to_id.items()},
                    "next_id": self._next_id,
                }, f)

    def add(self, chunk_ids: list[str], embeddings: list[list[float]]):
        """Add chunk vectors to the index."""
        if not embeddings:
            return

        emb_array = np.array(embeddings, dtype=np.float32)
        # Normalize for cosine similarity (inner product on unit vectors)
        faiss.normalize_L2(emb_array)

        dim = emb_array.shape[1]
        self._ensure_index(dim)

        faiss_ids = []
        for chunk_id in chunk_ids:
            fid = self._next_id
            self._next_id += 1
            self._id_to_faiss[chunk_id] = fid
            self._faiss_to_id[fid] = chunk_id
            faiss_ids.append(fid)

        self._index.add_with_ids(emb_array, np.array(faiss_ids, dtype=np.int64))
        self._save()

    def delete(self, chunk_ids: list[str]):
        """Remove chunk vectors from the index."""
        if not chunk_ids:
            return
        faiss_ids = [self._id_to_faiss[cid] for cid in chunk_ids if cid in self._id_to_faiss]
        if faiss_ids:
            self._index.remove_ids(np.array(faiss_ids, dtype=np.int64))
            for cid in chunk_ids:
                fid = self._id_to_faiss.pop(cid, None)
                if fid is not None:
                    self._faiss_to_id.pop(fid, None)
            self._save()

    def query(self, embedding: list[float], top_k: int = 20) -> list[dict]:
        """Retrieve top-k chunks. Returns [{chunk_id, score, index}, ...]."""
        if self._index is None or self._index.ntotal == 0:
            return []

        emb_array = np.array([embedding], dtype=np.float32)
        faiss.normalize_L2(emb_array)

        distances, indices = self._index.search(emb_array, top_k)

        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < 0:  # No more results
                break
            chunk_id = self._faiss_to_id.get(int(idx))
            if chunk_id:
                results.append({
                    "chunk_id": chunk_id,
                    "score": float(dist),
                    "index": i,
                })
        return results

    @property
    def count(self) -> int:
        return self._index.ntotal if self._index else 0


# Global singleton
_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def add_chunks(chunk_ids: list[str], embeddings: list[list[float]],
               texts: list[str], metadatas: list[dict]):
    """Add chunks to vector store. texts/metadatas kept for API compatibility;
    actual text/metadata is stored in SQLite."""
    get_store().add(chunk_ids, embeddings)


def delete_chunks(chunk_ids: list[str]):
    """Remove chunks from vector store."""
    get_store().delete(chunk_ids)


def query(embedding: list[float], top_k: int = 20) -> list[dict]:
    """Query vector store. Returns [{chunk_id, score}, ...]."""
    return get_store().query(embedding, top_k)
