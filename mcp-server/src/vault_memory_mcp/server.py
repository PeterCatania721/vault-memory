"""vault-memory MCP server (stdio)."""

from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import AppConfig, load_config, save_config
from .curator import VaultCurator
from .obsidian import keyword_search, list_notes, read_note
from .agent_memory import query_agent_guidance, write_agent_memory
from .provenance import (
    ProvenanceStore,
    build_research_frontmatter,
    hybrid_search,
    validate_frontmatter,
    write_research_note,
)
from .sync import VaultSync

mcp = FastMCP("vault-memory")

_config: AppConfig | None = None
_sync: VaultSync | None = None


def _get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def _state_dir() -> __import__("pathlib").Path:
    override = os.environ.get("VAULT_MEMORY_STATE_DIR")
    if override:
        return __import__("pathlib").Path(override)
    plugin_data = os.environ.get("GROK_PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return __import__("pathlib").Path(plugin_data)
    return __import__("pathlib").Path.home() / ".vault-memory"


def _get_sync() -> VaultSync:
    global _sync
    if _sync is None:
        _sync = VaultSync(_get_config(), state_dir=_state_dir())
    return _sync


def _get_curator() -> VaultCurator:
    sync = _get_sync()
    return VaultCurator(
        _get_config(),
        state_dir=_state_dir(),
        graph=sync.graph,
    )


def _record_usage(path: str, action: str) -> None:
    try:
        _get_curator().usage.record(path, action=action)
    except Exception:
        pass


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
    for field in (
        "enabled",
        "interval_hours",
        "stale_after_days",
        "archive_after_days",
        "compress_after_days",
        "compress_min_words",
        "compress_max_chars",
        "protect_paths",
        "protect_tags",
    ):
        if field in data.get("curator", {}):
            setattr(cfg.curator, field, data["curator"][field])
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
    _record_usage(path, "read")
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
    for hit in hits:
        if hit.get("path"):
            _record_usage(hit["path"], "keyword_search")
    return json.dumps({"query": query, "results": hits}, indent=2)


@mcp.tool()
def search_vault_semantic(query: str, limit: int = 10) -> str:
    """Semantic vector search via Neo4j Chunk embeddings."""
    sync = _get_sync()
    if not sync.graph:
        return json.dumps({"error": "Graph store disabled in config"})
    hits = sync.graph.search(query, limit=limit)
    for hit in hits:
        if hit.get("path"):
            _record_usage(hit["path"], "semantic_search")
    return json.dumps({"query": query, "results": hits}, indent=2)


@mcp.tool()
def search_vault_hybrid(query: str, limit: int = 5, depth: int = 2) -> str:
    """Default retrieval: semantic + graph neighbors + provenance trail per hit."""
    sync = _get_sync()
    if not sync.graph:
        return json.dumps({"error": "Graph store disabled in config"})
    hits = hybrid_search(sync.graph, query, limit=limit, depth=depth, vault_path=_get_config().vault.path)
    for hit in hits:
        if hit.get("path"):
            _record_usage(hit["path"], "hybrid_search")
    return json.dumps({"query": query, "results": hits}, indent=2)


@mcp.tool()
def upsert_note_provenance(path: str) -> str:
    """Create Fact/Source/TestRun nodes in Neo4j from note YAML frontmatter."""
    sync = _get_sync()
    if not sync.graph:
        return json.dumps({"error": "Graph store disabled in config"})
    cfg = _get_config()
    store = ProvenanceStore(sync.graph, cfg.vault.path)
    result = store.upsert_from_note(path)
    if result.get("ok"):
        sync.graph.upsert_note(read_note(cfg.vault.path, path))
    return json.dumps(result, indent=2)


@mcp.tool()
def add_research_memory(
    topic: str,
    body: str,
    source: str,
    source_type: str = "research",
    confidence: float = 0.8,
    spoil_after_days: int = 180,
    verification_json: str = "[]",
) -> str:
    """Write a provenance-structured Memory/Research-* note and sync graph."""
    cfg = _get_config()
    sync = _get_sync()
    slug = topic.lower().replace(" ", "-")[:60]
    day = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
    rel = f"Memory/Research-{slug}-{day}.md"
    verified = json.loads(verification_json) if verification_json.strip() else []
    fm = build_research_frontmatter(
        source=source,
        source_type=source_type,
        confidence=confidence,
        spoil_after_days=spoil_after_days,
        verified_in=verified,
        related_to=["[[Long-Term-Memory-Policy]]"],
    )
    issues = validate_frontmatter(fm, memory_note=True)
    if issues:
        return json.dumps({"ok": False, "issues": issues})
    write_research_note(cfg.vault.path, rel, topic, body, fm)
    prov = {"ok": False}
    curator_preview: dict[str, Any] | None = None
    if sync.graph:
        store = ProvenanceStore(sync.graph, cfg.vault.path)
        prov = store.upsert_from_note(rel)
        sync.run(force=False)
        curator_preview = _get_curator().run(dry_run=True).to_dict()
    return json.dumps(
        {"ok": True, "path": rel, "provenance": prov, "curator_preview": curator_preview},
        indent=2,
    )


@mcp.tool()
def add_agent_memory(
    title: str,
    body: str,
    memory_type: str,
    source: str,
    verification_json: str = "[]",
    contradicts_json: str = "[]",
    task_id: str = "",
    confidence: float = 0.85,
) -> str:
    """Write agentic task memory: solution (success), anti-pattern (failure to avoid), or lesson.

    Concrete recreation metadata (command, cwd, exit_code, expected, actual) goes in
    verification_json. Neo4j stores TestRun nodes; Obsidian stores abstract prose.
    memory_type: solution | anti-pattern | lesson
    """
    cfg = _get_config()
    sync = _get_sync()
    verified = json.loads(verification_json) if verification_json.strip() else []
    contradicts = json.loads(contradicts_json) if contradicts_json.strip() else []
    try:
        rel, fm, issues = write_agent_memory(
            cfg.vault.path,
            memory_type=memory_type.strip().lower(),
            title=title,
            body=body,
            source=source,
            verified_in=verified,
            contradicts=contradicts,
            task_id=task_id,
            confidence=confidence,
        )
    except ValueError as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    if issues:
        return json.dumps({"ok": False, "path": rel, "issues": issues})
    prov = {"ok": False}
    curator_preview: dict[str, Any] | None = None
    if sync.graph:
        store = ProvenanceStore(sync.graph, cfg.vault.path)
        prov = store.upsert_from_note(rel)
        sync.run(force=False)
        curator_preview = _get_curator().run(dry_run=True).to_dict()
    return json.dumps(
        {
            "ok": True,
            "path": rel,
            "memory_type": memory_type,
            "abstraction_layer": fm.get("abstraction_layer"),
            "provenance": prov,
            "curator_preview": curator_preview,
        },
        indent=2,
    )


@mcp.tool()
def query_agent_guidance_tool(query: str, limit: int = 5, depth: int = 2) -> str:
    """Optimized agentic retrieval: solutions to apply, anti-patterns to avoid, abstract lessons.

    Ranks by agent_score (success-boosted semantic). Concrete failures from Neo4j TestRun;
    abstract guidance from Obsidian Memory/Agent/ notes.
    """
    sync = _get_sync()
    if not sync.graph:
        return json.dumps({"error": "Graph store disabled in config"})
    result = query_agent_guidance(
        sync.graph,
        _get_config().vault.path,
        query,
        limit=limit,
        depth=depth,
    )
    for bucket in ("solutions", "anti_patterns", "lessons"):
        for hit in result.get(bucket, []):
            if hit.get("path"):
                _record_usage(hit["path"], "agent_guidance")
    return json.dumps(result, indent=2)


@mcp.tool()
def provenance_trail(path: str, depth: int = 2) -> str:
    """Return Fact → Source → TestRun chain for a vault note."""
    sync = _get_sync()
    if not sync.graph:
        return json.dumps({"error": "Graph store disabled in config"})
    store = ProvenanceStore(sync.graph, _get_config().vault.path)
    return json.dumps(store.provenance_trail(path, depth=depth), indent=2)


@mcp.tool()
def query_stale_facts(days: int = 90, source_type: str = "") -> str:
    """Facts with no successful verification in last N days (e.g. ossinsight)."""
    sync = _get_sync()
    if not sync.graph:
        return json.dumps({"error": "Graph store disabled in config"})
    store = ProvenanceStore(sync.graph, _get_config().vault.path)
    st = source_type.strip() or None
    rows = store.query_unverified_stale(days=days, source_type=st)
    return json.dumps({"days": days, "source_type": st, "facts": rows}, indent=2)


@mcp.tool()
def search_vault_graphrag(query: str, limit: int = 5, depth: int = 2) -> str:
    """GraphRAG: Neo4j vector search + wikilink graph context expansion."""
    sync = _get_sync()
    if not sync.graph:
        return json.dumps({"error": "Graph store disabled in config"})
    hits = sync.graph.search_with_graph_context(query, limit=limit, depth=depth)
    for hit in hits:
        if hit.get("path"):
            _record_usage(hit["path"], "graphrag_search")
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
    """Index vault into Neo4j (wikilinks + Chunk embeddings). Incremental by default."""
    result = _get_sync().run(force=force)
    return json.dumps(result.to_dict(), indent=2)


@mcp.tool()
def curator_status() -> str:
    """Return vault curator scheduler state, thresholds, and last run summary."""
    return json.dumps(_get_curator().status(), indent=2)


@mcp.tool()
def run_curator(dry_run: bool = False, force: bool = False) -> str:
    """Run Elon 5-step curator cycle: protect success data, archive stale, compress verbose notes."""
    curator = _get_curator()
    if not force and not dry_run:
        result = curator.maybe_run(dry_run=False)
        if result is None:
            return json.dumps(
                {
                    "skipped": True,
                    "reason": "interval not elapsed or curator paused/disabled",
                    "status": curator.status(),
                },
                indent=2,
            )
        return json.dumps(result.to_dict(), indent=2)
    return json.dumps(curator.run(dry_run=dry_run).to_dict(), indent=2)


@mcp.tool()
def curator_pin(path: str) -> str:
    """Pin a vault note so the curator never archives or compresses it."""
    _get_curator().pin_note(path)
    return json.dumps({"ok": True, "pinned": path}, indent=2)


@mcp.tool()
def curator_unpin(path: str) -> str:
    """Remove curator pin from a vault note."""
    _get_curator().unpin_note(path)
    return json.dumps({"ok": True, "unpinned": path}, indent=2)


@mcp.tool()
def curator_restore(path: str, stamp: str = "") -> str:
    """Restore an archived note from ~/.vault-memory/archive/ back into the vault."""
    result = _get_curator().restore_archived(path, stamp=stamp or None)
    return json.dumps(result, indent=2)


@mcp.tool()
def mark_vault_note_invalid(path: str, reason: str = "") -> str:
    """Mark a note as invalid/false/non-functional. Curator will archive it on next run."""
    return json.dumps(_get_curator().mark_invalid(path, reason=reason), indent=2)


@mcp.tool()
def set_vault_note_expiry(path: str, expires_at: str) -> str:
    """Set ISO expiration date on a note (e.g. 2026-12-31T00:00:00+00:00). Archives when expired."""
    return json.dumps(_get_curator().set_expiry(path, expires_at), indent=2)


@mcp.tool()
def delete_vault_note(path: str) -> str:
    """Archive a note immediately and purge vector/graph indexes (recoverable from archive/)."""
    result = _get_curator().delete_note(path)
    if result.get("ok"):
        _get_sync().run(force=False)
    return json.dumps(result, indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()