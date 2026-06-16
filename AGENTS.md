# vault-memory — agent rules

## Stack (only proven patterns)

- Obsidian vault = markdown on disk (no proprietary API)
- Qdrant v1.12.5 for vectors
- Neo4j 5.26 for wikilink graph
- sentence-transformers/all-MiniLM-L6-v2 local embeddings
- MCP stdio child process (no network MCP for local data)

## Software 3.0 (Karpathy)

Agents may **configure the system in natural language**:

1. `get_config` → understand current state
2. `update_config` → change vault path, DB URLs, chunk size
3. `sync_vault` → apply changes

Never hand-edit Docker images without pinning versions in `docker/`.

## Development

```bash
git worktree add ../vault-memory-feature my-branch
bash scripts/test-cycle.sh
```

Unit tests: no Docker. Integration: `pytest -m integration` (needs Docker).

## Cross-agent paths

| Agent | Plugin install | MCP config |
|-------|----------------|------------|
| Grok Build | `grok plugin install . --trust` | `.mcp.json` auto |
| Claude Code | `/plugin` local path | `.mcp.json` auto |
| Hermes | `scripts/setup-hermes.sh` | `~/.hermes/config.yaml` |