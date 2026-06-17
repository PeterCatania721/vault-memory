---
name: vault-memory-sync
description: >
  Sync Obsidian vault into Neo4j (wikilinks + chunk embeddings + provenance). Use after
  editing notes, on schedule, or when user asks to index/refresh/reindex vault memory.
  Triggers on sync vault, reindex, update embeddings, refresh knowledge graph.
---

# vault-memory Sync

Indexes vault markdown into **Neo4j** (single store — no Qdrant).

## When to sync

- After bulk note edits in Obsidian
- After changing `vault.path` or chunk settings
- After `add_research_memory` or frontmatter backfill
- When hybrid/semantic search returns stale results

## MCP tools

1. `health_check` — confirm Neo4j up
2. `sync_vault` — incremental (default, uses content hash)
3. `sync_vault` with `force: true` — full reindex
4. `upsert_note_provenance` — refresh Fact/Source graph for Memory/ notes

## Expected output

```json
{"indexed": 12, "skipped": 340, "pruned": 0, "errors": []}
```

If `errors` is non-empty, read each path, fix vault or DB connectivity, re-run.

## Incremental logic

Only changed files (SHA256 hash) are re-embedded. Wikilinks and provenance rebuilt per changed note.

## Docker

If sync fails on connection:

```bash
bash scripts/docker-up.sh
```