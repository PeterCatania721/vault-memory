"""Neo4j knowledge graph — Note nodes + wikilink edges."""

from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

from .config import GraphConfig
from .obsidian import Note

READ_ONLY_PREFIXES = ("MATCH", "RETURN", "WITH", "OPTIONAL")


class GraphStore:
    def __init__(self, config: GraphConfig):
        self.config = config
        self._driver = GraphDatabase.driver(
            config.uri,
            auth=(config.user, config.password),
        )

    def close(self) -> None:
        self._driver.close()

    def upsert_note(self, note: Note) -> None:
        with self._driver.session(database=self.config.database) as session:
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

    def neighbors(self, path: str, depth: int = 1) -> list[dict[str, Any]]:
        depth = max(1, min(depth, 3))
        query = f"""
        MATCH (n:Note {{path: $path}})
        OPTIONAL MATCH path = (n)-[:LINKS_TO*1..{depth}]-(m:Note)
        RETURN DISTINCT m.path AS path, m.title AS title
        LIMIT 50
        """
        with self._driver.session(database=self.config.database) as session:
            rows = session.run(query, path=path)
            return [{"path": r["path"], "title": r["title"]} for r in rows if r["path"]]

    def query_readonly(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        normalized = cypher.strip().upper()
        forbidden = ("CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP", "DETACH")
        if any(word in normalized for word in forbidden):
            raise ValueError("Only read-only Cypher queries are allowed.")
        if not normalized.startswith(READ_ONLY_PREFIXES):
            raise ValueError("Query must start with MATCH, RETURN, WITH, or OPTIONAL.")
        with self._driver.session(database=self.config.database) as session:
            result = session.run(cypher, **(params or {}))
            return [dict(record) for record in result]

    def health(self) -> dict[str, Any]:
        try:
            with self._driver.session(database=self.config.database) as session:
                count = session.run("MATCH (n:Note) RETURN count(n) AS c").single()["c"]
            return {"ok": True, "notes": count, "uri": self.config.uri}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "uri": self.config.uri}