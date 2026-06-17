---
description: Sync Obsidian vault into Neo4j (graph + vectors) via vault-memory MCP
---

Run the vault-memory sync workflow:

1. Invoke skill `vault-memory-sync`
2. Call MCP `health_check`
3. Call MCP `sync_vault` (force if user said reindex)
4. Report indexed/skipped/pruned/errors counts