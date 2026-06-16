"""vault-memory MCP server (stdio)."""

from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import AppConfig, load_config, save_config
from .obsidian import keyword_search, list_notes, read_note
from .sync import VaultSync

mcp = FastMCP("vault-memory")

_config: AppConfig | None = None
_sync: VaultSync | None = None


def _get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def _get_sync() -> VaultSync:
    global _sync
    if _sync is None:
        plugin_data = os.environ.get("GROK_PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
        state_dir = None
        if plugin_data:
            state_dir = __import__("pathlib").Path(plugin_data)
        _sync = VaultSync(_get_config(), state_dir=state_dir)
    return _sync


@mcp.tool()
def health_check() -> str:
    """Check vault path and database connectivity."""
    return json.dumps(_get_sync().health(), indent=2)


@mcp.tool()
def get_config() -> str:
    """Return current vault-memory configuration (Software 3.0: AI reads then edits)."""
    return json.dumps(_get_config().to_dict(), indent=2)


@mcp.tool()
def update_config(updates_json: str) -> str:
    """Merge partial config updates and save. Pass JSON object with keys: vault, vector, graph, sync, docker."""
    cfg = _get_config()
    updates = json.loads(updates_json)
    data = cfg.to_dict()
    for key, value in updates.items():
        if isinstance(value, dict) and key in data:
            data[key].update(value)
        else:
            data[key] = value
    cfg.vault.path = __import__("pathlib").Path(
        os.path.expanduser(data["vault"]["path"])
    ).resolve()
    cfg.vault.ignore = data["vault"].get("ignore", cfg.vault.ignore)
    for field in ("enabled", "url", "collection", "embedding_model", "chunk_size", "chunk_overlap"):
        if field in data.get("vector", {}):
            setattr(cfg.vector, field, data["vector"][field])
    for field in ("enabled", "uri", "user", "password", "database"):
        if field in data.get("graph", {}):
            setattr(cfg.graph, field, data["graph"][field])
    save_config(cfg)
    global _config, _sync
    _config = cfg
    _sync = None
    return json.dumps({"ok": True, "config_path": str(cfg.config_path)}, indent=2)


@mcp.tool()
def list_vault_notes() -> str:
    """List all markdown notes in the Obsidian vault."""
    cfg = _get_config()
    notes = list_notes(cfg.vault.path, cfg.vault.ignore)
    return json.dumps({"count": len(notes), "notes": notes}, indent=2)


@mcp.tool()
def read_vault_note(path: str) -> str:
    """Read a single note by relative path."""
    cfg = _get_config()
    note = read_note(cfg.vault.path, path)
    return json.dumps(
        {
            "path": note.path,
            "title": note.title,
            "content": note.content,
            "wikilinks": note.wikilinks,
        },
        indent=2,
    )


@mcp.tool()
def search_vault_keyword(query: str, limit: int = 10) -> str:
    """Full-text keyword search across vault markdown files."""
    cfg = _get_config()
    hits = keyword_search(cfg.vault.path, query, cfg.vault.ignore, limit=limit)
    return json.dumps({"query": query, "results": hits}, indent=2)


@mcp.tool()
def search_vault_semantic(query: str, limit: int = 10) -> str:
    """Semantic vector search via Qdrant embeddings."""
    sync = _get_sync()
    if not sync.vector:
        return json.dumps({"error": "Vector store disabled in config"})
    hits = sync.vector.search(query, limit=limit)
    return json.dumps({"query": query, "results": hits}, indent=2)


@mcp.tool()
def graph_neighbors(path: str, depth: int = 1) -> str:
    """Return linked notes around a vault path using Neo4j wikilink graph."""
    sync = _get_sync()
    if not sync.graph:
        return json.dumps({"error": "Graph store disabled in config"})
    neighbors = sync.graph.neighbors(path, depth=depth)
    return json.dumps({"path": path, "neighbors": neighbors}, indent=2)


@mcp.tool()
def graph_query(cypher: str) -> str:
    """Run a read-only Cypher query against the Neo4j knowledge graph."""
    sync = _get_sync()
    if not sync.graph:
        return json.dumps({"error": "Graph store disabled in config"})
    rows = sync.graph.query_readonly(cypher)
    return json.dumps({"rows": rows}, indent=2)


@mcp.tool()
def sync_vault(force: bool = False) -> str:
    """Index vault into Qdrant vectors and Neo4j graph. Incremental by default."""
    result = _get_sync().run(force=force)
    return json.dumps(result.to_dict(), indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()