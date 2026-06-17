"""Shared sentence-transformer embeddings for Neo4j vector properties."""

from __future__ import annotations

_EMBEDDER = None
_MODEL_NAME: str | None = None


def embedder(model_name: str):
    global _EMBEDDER, _MODEL_NAME
    if _EMBEDDER is None or _MODEL_NAME != model_name:
        from sentence_transformers import SentenceTransformer

        _EMBEDDER = SentenceTransformer(model_name)
        _MODEL_NAME = model_name
    return _EMBEDDER


def vector_size(model_name: str) -> int:
    return embedder(model_name).get_sentence_embedding_dimension()


def embed_texts(model_name: str, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = embedder(model_name)
    return model.encode(texts, normalize_embeddings=True).tolist()