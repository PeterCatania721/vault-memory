---
description: Sync Obsidian vault into Qdrant and Neo4j via vault-memory MCP
---

Run the vault-memory sync workflow:

1. Invoke skill `vault-memory-sync`
2. Call MCP `health_check`
3. Call MCP `sync_vault` (force if user said reindex)
4. Report indexed/skipped/errors counts