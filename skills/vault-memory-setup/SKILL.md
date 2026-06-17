---
name: vault-memory-setup
description: >
  Install and configure vault-memory (Obsidian + Neo4j graph/vector). Use when setting up
  the plugin, starting Docker, editing ~/.vault-memory/config.yaml, or runs
  /vault-memory-setup. Software 3.0 — read config with get_config, update with update_config.
---

# vault-memory Setup

Stack: **Obsidian markdown vault** (source of truth) → **Neo4j** (wikilinks + chunk embeddings + provenance graph) → **MCP stdio** (Grok, Claude Code, Hermes).

**v0.2+:** One Docker container (Neo4j). Qdrant is not used.

## Quick install

```bash
cd /path/to/vault-memory
bash scripts/install.sh
bash scripts/docker-up.sh
```

Edit `~/.vault-memory/config.yaml`:

```yaml
vault:
  path: ~/Documents/Obsidian Vault
vector:
  enabled: true
  provider: neo4j
graph:
  enabled: true
  uri: bolt://127.0.0.1:7687
```

## Grok Build

```bash
grok plugin install /path/to/vault-memory --trust
```

Trust activates MCP + hooks. Open `/mcps` and confirm `vault-memory` is connected.

## Claude Code

`/plugin` → Add plugin → local path `/path/to/vault-memory` → trust MCP.

## Hermes Agent

```bash
bash scripts/setup-hermes.sh
hermes mcp test vault_memory
```

## Cursor

```bash
bash scripts/setup-cursor.sh
```

Opens **`.cursor/mcp.json`** in the repo (uses `${workspaceFolder}/mcp-server`). Restart Cursor, then **Settings → Tools & MCP** → enable `vault-memory`.

Optional global install: copy `.cursor/mcp.json` to `~/.cursor/mcp.json` and replace `${workspaceFolder}` with the absolute repo path.

## Docker

```bash
bash scripts/docker-up.sh
```

On restricted cloud VMs, `docker-up.sh` starts dockerd with `vfs` storage if needed.

Legacy Qdrant containers are not used — remove with `docker rm -f qdrant` if present.

## Verify

Call MCP `health_check`. Expect: vault path OK, `store: neo4j`, graph + vector OK.

Then `sync_vault force=true` once to index notes.