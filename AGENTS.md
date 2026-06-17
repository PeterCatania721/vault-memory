# vault-memory — agent rules

## Stack (only proven patterns)

- Obsidian vault = markdown on disk (no proprietary API)
- **Neo4j 5.26** — wikilinks, chunk embeddings, verification embeddings, provenance graph
- sentence-transformers/all-MiniLM-L6-v2 local embeddings (stored on Neo4j nodes)
- MCP stdio child process (no network MCP for local data)
- **Qdrant removed in v0.2+** — do not add back without explicit user request

## Software 3.0 (Karpathy)

Agents may **configure the system in natural language**:

1. `get_config` → understand current state
2. `update_config` → change vault path, Neo4j URI, chunk size
3. `sync_vault` → apply changes

Never hand-edit Docker images without pinning versions in `docker/`.

## Default retrieval

1. `query_agent_guidance` — before agentic tasks (solutions + anti-patterns)
2. `search_vault_hybrid` — general retrieval
3. `provenance_trail` when citing numbers or sources
4. `graph_neighbors` for related notes

## Agent memory write

After task execution, use `add_agent_memory`:
- `memory_type: solution` + `verified_in` with command/cwd/exit_code on success
- `memory_type: anti-pattern` + failure recreation metadata on failure cases A–F

## Development

```bash
git worktree add ../vault-memory-feature my-branch
bash scripts/test-cycle.sh
```

Unit tests: no Docker. Integration: `pytest -m integration` (needs Neo4j Docker).

## After every change (mandatory)

1. Update docs if behavior/architecture/tools changed: `README.md`, `STATUS.md`, `RELEASE-NOTES.md`, skills, `AGENTS.md`
2. Run tests (`bash scripts/test-cycle.sh` or targeted pytest)
3. **Save test memory** — success **and** failure — to Obsidian `Memory/` with full recreation metadata (`verified_in`: command, cwd, exit_code, expected/actual, versions, git commit, containers/volumes). Policy: vault note `Test-Memory-Recreation-Policy`. Use `scripts/add_research_memory.py` or MCP `add_research_memory`, then sync.
4. `git add` → `git commit` → `git push` (`gh auth setup-git`)

Never leave the repo out of sync with the code.

## Cross-agent paths

| Agent | Plugin install | MCP config |
|-------|----------------|------------|
| Grok Build | `grok plugin install . --trust` | `.mcp.json` auto |
| Claude Code | `/plugin` local path | `.mcp.json` auto |
| Hermes | `scripts/setup-hermes.sh` | `~/.hermes/config.yaml` |