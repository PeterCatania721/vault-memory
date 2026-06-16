"""Qdrant vector store — proven RAG stack."""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from .config import VectorConfig
from .obsidian import Note, chunk_text

_EMBEDDER = None


def _embedder(model_name: str):
    global _EMBEDDER
    if _EMBEDDER is None or getattr(_EMBEDDER, "_model_name", None) != model_name:
        from sentence_transformers import SentenceTransformer

        _EMBEDDER = SentenceTransformer(model_name)
        _EMBEDDER._model_name = model_name  # type: ignore[attr-defined]
    return _EMBEDDER


def _vector_size(model_name: str) -> int:
    return _embedder(model_name).get_sentence_embedding_dimension()


class VectorStore:
    def __init__(self, config: VectorConfig):
        self.config = config
        self.client = QdrantClient(url=config.url)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        size = _vector_size(self.config.embedding_model)
        collections = {c.name for c in self.client.get_collections().collections}
        if self.config.collection not in collections:
            self.client.create_collection(
                collection_name=self.config.collection,
                vectors_config=qm.VectorParams(size=size, distance=qm.Distance.COSINE),
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = _embedder(self.config.embedding_model)
        return model.encode(texts, normalize_embeddings=True).tolist()

    def upsert_note(self, note: Note) -> int:
        chunks = chunk_text(
            note.content,
            self.config.chunk_size,
            self.config.chunk_overlap,
        )
        if not chunks:
            return 0
        vectors = self.embed(chunks)
        points: list[qm.PointStruct] = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{note.path}:{i}:{note.content_hash}"))
            points.append(
                qm.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "path": note.path,
                        "title": note.title,
                        "chunk_index": i,
                        "text": chunk,
                        "content_hash": note.content_hash,
                    },
                )
            )
        self.client.upsert(collection_name=self.config.collection, points=points)
        return len(points)

    def delete_note(self, path: str) -> None:
        self.client.delete(
            collection_name=self.config.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[qm.FieldCondition(key="path", match=qm.MatchValue(value=path))]
                )
            ),
        )

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        vector = self.embed([query])[0]
        hits = self.client.search(
            collection_name=self.config.collection,
            query_vector=vector,
            limit=limit,
            with_payload=True,
        )
        return [
            {
                "path": hit.payload.get("path"),
                "title": hit.payload.get("title"),
                "text": hit.payload.get("text"),
                "score": float(hit.score),
            }
            for hit in hits
        ]

    def health(self) -> dict[str, Any]:
        try:
            info = self.client.get_collection(self.config.collection)
            return {
                "ok": True,
                "collection": self.config.collection,
                "points": info.points_count,
                "url": self.config.url,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "url": self.config.url}