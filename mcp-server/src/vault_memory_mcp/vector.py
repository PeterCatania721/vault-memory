"""Deprecated — vectors are stored on Neo4j nodes via GraphStore."""

from __future__ import annotations

from .graph import GraphStore

# Backward-compatible alias for scripts importing VectorStore
VectorStore = GraphStore