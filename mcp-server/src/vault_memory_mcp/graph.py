"""Neo4j unified store — graph structure + vector embeddings on nodes."""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import GraphDatabase

from .config import GraphConfig, VectorConfig
from .embeddings import embed_texts, vector_size
from .obsidian import Note, chunk_text

READ_ONLY_PREFIXES = ("MATCH", "RETURN", "WITH", "OPTIONAL", "CALL")

VAULT_CHUNK_INDEX = "vault_chunk_embeddings"
VERIFICATION_INDEX = "verification_embeddings"


class GraphStore:
    """Neo4j graph + vector index (GraphRAG-ready)."""

    def __init__(self, config: GraphConfig, vector: VectorConfig | None = None):
        self.config = config
        self.vector = vector
        self._vectors_enabled = bool(vector and vector.enabled)
        self._driver = GraphDatabase.driver(
            config.uri,
            auth=(config.user, config.password),
        )
        if self._vectors_enabled:
            self._ensure_vector_indexes()

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None  # type: ignore[assignment]

    def __enter__(self) -> GraphStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _session(self):
        return self._driver.session(database=self.config.database)

    def _ensure_vector_indexes(self) -> None:
        assert self.vector is not None
        dim = vector_size(self.vector.embedding_model)
        with self._session() as session:
            session.run(
                f"""
                CREATE VECTOR INDEX {VAULT_CHUNK_INDEX} IF NOT EXISTS
                FOR (c:Chunk)
                ON c.embedding
                OPTIONS {{
                  indexConfig: {{
                    `vector.dimensions`: {dim},
                    `vector.similarity_function`: 'cosine'
                  }}
                }}
                """
            )
            session.run(
                f"""
                CREATE VECTOR INDEX {VERIFICATION_INDEX} IF NOT EXISTS
                FOR (v:Verification)
                ON v.embedding
                OPTIONS {{
                  indexConfig: {{
                    `vector.dimensions`: {dim},
                    `vector.similarity_function`: 'cosine'
                  }}
                }}
                """
            )

    def _chunk_id(self, path: str, chunk_index: int, content_hash: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{path}:{chunk_index}:{content_hash}"))

    def upsert_note(self, note: Note) -> int:
        chunks_written = 0
        with self._session() as session:
            session.run(
                """
                MERGE (n:Note {path: $path})
                SET n.title = $title,
                    n.content_hash = $content_hash,
                    n.updated_at = timestamp()
                """,
                path=note.path,
                title=note.title,
                content_hash=note.content_hash,
            )
            if note.wikilinks:
                session.run(
                    """
                    MATCH (src:Note {path: $path})
                    OPTIONAL MATCH (src)-[r:LINKS_TO]->()
                    DELETE r
                    """,
                    path=note.path,
                )
                for target in note.wikilinks:
                    session.run(
                        """
                        MERGE (src:Note {path: $path})
                        MERGE (dst:Note {title: $target})
                        ON CREATE SET dst.path = $target
                        MERGE (src)-[:LINKS_TO]->(dst)
                        """,
                        path=note.path,
                        target=target,
                    )

            if self._vectors_enabled and self.vector is not None:
                session.run(
                    """
                    MATCH (n:Note {path: $path})-[:HAS_CHUNK]->(c:Chunk)
                    DETACH DELETE c
                    """,
                    path=note.path,
                )
                chunks = chunk_text(
                    note.content,
                    self.vector.chunk_size,
                    self.vector.chunk_overlap,
                )
                if chunks:
                    vectors = embed_texts(self.vector.embedding_model, chunks)
                    rows = [
                        {
                            "id": self._chunk_id(note.path, i, note.content_hash),
                            "chunk_index": i,
                            "text": chunk,
                            "embedding": vector,
                        }
                        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
                    ]
                    session.run(
                        """
                        MATCH (n:Note {path: $path})
                        UNWIND $rows AS row
                        CREATE (c:Chunk {
                            id: row.id,
                            path: $path,
                            title: $title,
                            chunk_index: row.chunk_index,
                            text: row.text,
                            content_hash: $content_hash,
                            record_type: 'vault_chunk',
                            embedding: row.embedding
                        })
                        MERGE (n)-[:HAS_CHUNK]->(c)
                        """,
                        path=note.path,
                        title=note.title,
                        content_hash=note.content_hash,
                        rows=rows,
                    )
                    chunks_written = len(rows)
        return chunks_written

    def delete_note(self, path: str) -> None:
        with self._session() as session:
            session.run(
                """
                MATCH (n:Note {path: $path})
                OPTIONAL MATCH (n)-[:HAS_CHUNK]->(c:Chunk)
                DETACH DELETE c, n
                """,
                path=path,
            )

    def list_paths(self) -> list[str]:
        with self._session() as session:
            rows = session.run(
                "MATCH (n:Note) WHERE n.path IS NOT NULL RETURN DISTINCT n.path AS path"
            )
            return [r["path"] for r in rows if r.get("path")]

    def neighbors(self, path: str, depth: int = 1) -> list[dict[str, Any]]:
        depth = max(1, min(depth, 3))
        query = f"""
        MATCH (n:Note {{path: $path}})
        OPTIONAL MATCH path = (n)-[:LINKS_TO*1..{depth}]-(m:Note)
        RETURN DISTINCT m.path AS path, m.title AS title
        LIMIT 50
        """
        with self._session() as session:
            rows = session.run(query, path=path)
            return [{"path": r["path"], "title": r["title"]} for r in rows if r["path"]]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Semantic search over vault Chunk embeddings in Neo4j."""
        if not self._vectors_enabled or self.vector is None:
            return []
        vector = embed_texts(self.vector.embedding_model, [query])[0]
        with self._session() as session:
            rows = session.run(
                f"""
                CALL db.index.vector.queryNodes('{VAULT_CHUNK_INDEX}', $limit, $vector)
                YIELD node AS chunk, score
                WHERE chunk.record_type = 'vault_chunk'
                MATCH (note:Note)-[:HAS_CHUNK]->(chunk)
                RETURN score, note.path AS path, note.title AS title, chunk.text AS text
                ORDER BY score DESC
                """,
                limit=limit,
                vector=vector,
            )
            return [
                {
                    "path": r["path"],
                    "title": r["title"],
                    "text": r["text"],
                    "score": float(r["score"]),
                }
                for r in rows
            ]

    def search_with_graph_context(
        self, query: str, limit: int = 5, depth: int = 2
    ) -> list[dict[str, Any]]:
        """GraphRAG pattern: vector search then expand wikilink neighborhood."""
        if not self._vectors_enabled or self.vector is None:
            return []
        depth = max(1, min(depth, 3))
        vector = embed_texts(self.vector.embedding_model, [query])[0]
        with self._session() as session:
            rows = session.run(
                f"""
                CALL db.index.vector.queryNodes('{VAULT_CHUNK_INDEX}', $limit, $vector)
                YIELD node AS chunk, score
                WHERE chunk.record_type = 'vault_chunk'
                MATCH (note:Note)-[:HAS_CHUNK]->(chunk)
                OPTIONAL MATCH (note)-[:LINKS_TO*1..{depth}]-(related:Note)
                RETURN score,
                       note.path AS path,
                       note.title AS title,
                       chunk.text AS text,
                       collect(DISTINCT related.path) AS related_paths,
                       collect(DISTINCT related.title) AS related_titles
                ORDER BY score DESC
                """,
                limit=limit,
                vector=vector,
            )
            return [
                {
                    "path": r["path"],
                    "title": r["title"],
                    "text": r["text"],
                    "score": float(r["score"]),
                    "related_paths": [p for p in (r["related_paths"] or []) if p],
                    "related_titles": [t for t in (r["related_titles"] or []) if t],
                }
                for r in rows
            ]

    def query_readonly(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        normalized = cypher.strip().upper()
        forbidden = ("CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP", "DETACH")
        if any(word in normalized for word in forbidden):
            raise ValueError("Only read-only Cypher queries are allowed.")
        if not normalized.startswith(READ_ONLY_PREFIXES):
            raise ValueError("Query must start with MATCH, RETURN, WITH, OPTIONAL, or CALL.")
        with self._session() as session:
            result = session.run(cypher, **(params or {}))
            return [dict(record) for record in result]

    def health(self) -> dict[str, Any]:
        try:
            with self._session() as session:
                notes = session.run("MATCH (n:Note) RETURN count(n) AS c").single()["c"]
                chunks = session.run(
                    "MATCH (c:Chunk {record_type: 'vault_chunk'}) RETURN count(c) AS c"
                ).single()["c"]
                verifications = session.run(
                    "MATCH (v:Verification) WHERE v.embedding IS NOT NULL RETURN count(v) AS c"
                ).single()["c"]
            vector_info = {
                "ok": True,
                "provider": "neo4j",
                "chunks": chunks,
                "verifications_indexed": verifications,
                "chunk_index": VAULT_CHUNK_INDEX,
                "verification_index": VERIFICATION_INDEX,
            }
            if self.vector is not None:
                vector_info["embedding_model"] = self.vector.embedding_model
            return {
                "ok": True,
                "notes": notes,
                "uri": self.config.uri,
                "vector": vector_info,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "uri": self.config.uri}