---
name: vault-memory-query
description: >
  Query Obsidian vault memory via hybrid GraphRAG, agent guidance, provenance trails, or Neo4j graph.
  Use when user asks about past notes, decisions, linked concepts, task execution, or "what did I write about X".
  Triggers on search vault, find in obsidian, knowledge graph, related notes, what to avoid, successful solution.
---

# vault-memory Query

## Tool selection (proven pattern)

| Need | MCP tool |
|------|----------|
| **Agent task execution** | `query_agent_guidance` |
| **Default retrieval** | `search_vault_hybrid` |
| Provenance audit chain | `provenance_trail` |
| Stale/unverified facts | `query_stale_facts` |
| Exact term / title | `search_vault_keyword` |
| Concept / paraphrase | `search_vault_semantic` |
| Full note body | `read_vault_note` |
| Related notes | `graph_neighbors` |
| Custom graph query | `graph_query` (read-only Cypher) |
| Write research | `add_research_memory` |
| Write agent memory | `add_agent_memory` |

## Two-tier memory (agentic systems)

| Layer | Store | Content |
|-------|-------|---------|
| Concrete | Neo4j `:TestRun` | command, cwd, exit_code, expected, actual, outcome |
| Abstract | Obsidian `Memory/Agent/` | Solutions, anti-patterns, lessons |

## Recommended agent flow

1. **Before task:** `query_agent_guidance` — solutions + anti-patterns ranked by `agent_score`
2. **During:** `search_vault_hybrid` for broader context
3. **After success:** `add_agent_memory` with `memory_type: solution` + `verified_in` recreation metadata
4. **After failure:** `add_agent_memory` with `memory_type: anti-pattern` + failure cases
5. `provenance_trail` when citing numbers or sources

## Recommended flow (hybrid default)

1. `search_vault_hybrid` with user question (top 5)
2. `provenance_trail` on best hit when citing numbers or sources
3. `graph_neighbors` for related context
4. `read_vault_note` for full text when drafting answer

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