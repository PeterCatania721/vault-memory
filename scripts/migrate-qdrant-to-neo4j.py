#!/usr/bin/env python3
"""One-shot migration: Qdrant vault_memory + vault_verifications → Neo4j."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-server" / "src"))

from vault_memory_mcp.config import load_config
from vault_memory_mcp.embeddings import embed_texts
from vault_memory_mcp.graph import GraphStore, VERIFICATION_INDEX


def _qdrant_client():
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        print("qdrant-client not installed — skip migration or: pip install qdrant-client")
        return None
    return QdrantClient(url="http://127.0.0.1:6333")


def migrate_vault_chunks(graph: GraphStore, client, collection: str) -> int:
    from vault_memory_mcp.obsidian import Note

    migrated = 0
    offset = None
    while True:
        records, offset = client.scroll(collection_name=collection, limit=128, offset=offset, with_payload=True)
        for point in records:
            payload = point.payload or {}
            path = payload.get("path")
            text = payload.get("text")
            if not path or not text:
                continue
            note = Note(
                path=str(path),
                title=str(payload.get("title") or path),
                content=text,
                mtime=0.0,
                content_hash=str(payload.get("content_hash") or "migrated"),
                wikilinks=[],
            )
            graph.upsert_note(note)
            migrated += 1
        if offset is None:
            break
    return migrated


def migrate_verifications(graph: GraphStore, client, collection: str, model: str) -> int:
    migrated = 0
    offset = None
    while True:
        records, offset = client.scroll(collection_name=collection, limit=128, offset=offset, with_payload=True)
        for point in records:
            payload = point.payload or {}
            if payload.get("record_type") != "verification_granular":
                continue
            granular_text = payload.get("text") or json.dumps(payload, sort_keys=True)
            embedding = embed_texts(model, [granular_text])[0]
            with graph._session() as session:
                session.run(
                    f"""
                    MATCH (v:Verification {{mcp_name: $mcp, test_name: $test_name, test_type: $test_type}})
                    SET v.evidence_json = $evidence_json,
                        v.embedding = $embedding,
                        v.record_type = 'verification_granular'
                    """,
                    mcp=payload.get("mcp_name"),
                    test_name=payload.get("test_name"),
                    test_type=payload.get("test_type"),
                    evidence_json=granular_text,
                    embedding=embedding,
                )
            migrated += 1
        if offset is None:
            break
    return migrated


def main() -> int:
    cfg = load_config()
    client = _qdrant_client()
    if client is None:
        return 1

    with GraphStore(cfg.graph, cfg.vector) as graph:
        vault_migrated = 0
        verify_migrated = 0
        collections = {c.name for c in client.get_collections().collections}
        if "vault_memory" in collections:
            vault_migrated = migrate_vault_chunks(graph, client, "vault_memory")
        if "vault_verifications" in collections:
            verify_migrated = migrate_verifications(
                graph, client, "vault_verifications", cfg.vector.embedding_model
            )

    print(
        json.dumps(
            {
                "ok": True,
                "vault_chunks_migrated": vault_migrated,
                "verifications_backfilled": verify_migrated,
                "verification_index": VERIFICATION_INDEX,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())