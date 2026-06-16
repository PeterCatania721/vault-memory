---
name: vault-memory-query
description: >
  Query Obsidian vault memory via keyword search, semantic vector search, or Neo4j graph.
  Use when user asks about past notes, decisions, linked concepts, or "what did I write about X".
  Triggers on search vault, find in obsidian, knowledge graph, related notes.
---

# vault-memory Query

## Tool selection (proven pattern)

| Need | MCP tool |
|------|----------|
| Exact term / title | `search_vault_keyword` |
| Concept / paraphrase | `search_vault_semantic` |
| Full note body | `read_vault_note` |
| Related notes | `graph_neighbors` |
| Custom graph query | `graph_query` (read-only Cypher) |

## Recommended flow

1. `search_vault_semantic` with user question (top 5)
2. `graph_neighbors` on best hit for context
3. `read_vault_note` for full text when drafting answer

## Example graph query

```cypher
MATCH (n:Note)-[:LINKS_TO]->(m:Note)
WHERE n.path CONTAINS 'project'
RETURN n.title, m.title LIMIT 20
```

Pass to `graph_query` — writes are blocked for safety.

## Software 3.0

If results are poor, use `get_config` → adjust `chunk_size` or `embedding_model` via `update_config` → `sync_vault force=true`.