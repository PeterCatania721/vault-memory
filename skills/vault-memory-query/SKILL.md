---
name: vault-memory-query
description: >
  Query Obsidian vault memory via hybrid GraphRAG, provenance trails, or Neo4j graph.
  Use when user asks about past notes, decisions, linked concepts, or "what did I write about X".
  Triggers on search vault, find in obsidian, knowledge graph, related notes.
---

# vault-memory Query

## Tool selection (proven pattern)

| Need | MCP tool |
|------|----------|
| **Default retrieval** | `search_vault_hybrid` |
| Provenance audit chain | `provenance_trail` |
| Stale/unverified facts | `query_stale_facts` |
| Exact term / title | `search_vault_keyword` |
| Concept / paraphrase | `search_vault_semantic` |
| Full note body | `read_vault_note` |
| Related notes | `graph_neighbors` |
| Custom graph query | `graph_query` (read-only Cypher) |
| Write research | `add_research_memory` |

## Recommended flow (hybrid default)

1. `search_vault_hybrid` with user question (top 5)
2. `provenance_trail` on best hit when citing numbers or sources
3. `graph_neighbors` for related context
4. `read_vault_note` for full text when drafting answer
5. Cross-check Hermes built-in `memory` for compact facts

## Example graph queries

```cypher
MATCH (n:Note)-[:LINKS_TO]->(m:Note)
WHERE n.path CONTAINS 'project'
RETURN n.title, m.title LIMIT 20
```

```text
query_stale_facts(days=60, source_type="ossinsight")
```

Pass Cypher to `graph_query` — writes are blocked for safety.

## Software 3.0

If results are poor, use `get_config` → adjust `chunk_size` or `embedding_model` via `update_config` → `sync_vault force=true`.