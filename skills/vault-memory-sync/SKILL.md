---
name: vault-memory-sync
description: >
  Sync Obsidian vault into Qdrant vectors and Neo4j graph. Use after editing notes,
  on schedule, or when user asks to index/refresh/reindex vault memory. Triggers on
  sync vault, reindex, update embeddings, refresh knowledge graph.
---

# vault-memory Sync

## When to sync

- After bulk note edits in Obsidian
- After changing `vault.path` or chunk settings
- When semantic search returns stale results

## MCP tools

1. `health_check` — confirm backends up
2. `sync_vault` — incremental (default, uses content hash)
3. `sync_vault` with `force: true` — full reindex

## Expected output

```json
{"indexed": 12, "skipped": 340, "errors": []}
```

If `errors` is non-empty, read each path, fix vault or DB connectivity, re-run.

## Incremental logic

Only changed files (SHA256 hash) are re-embedded. Wikilinks rebuilt per changed note.

## Docker

If sync fails on connection, run:

```bash
bash scripts/docker-up.sh
```