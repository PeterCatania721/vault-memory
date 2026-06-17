"""Integration tests — require Neo4j (pytest -m integration)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from vault_memory_mcp.config import load_config
from vault_memory_mcp.curator import VaultCurator
from vault_memory_mcp.docker_health import ensure_docker_services, services_healthy
from vault_memory_mcp.sync import VaultSync

from conftest import FIXTURE_IGNORE, FIXTURES, PROJECT_ROOT, fixture_note_count

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def integration_config(tmp_path_factory):
    if os.environ.get("VAULT_MEMORY_SKIP_DOCKER") == "1":
        pytest.skip("Docker integration skipped (VAULT_MEMORY_SKIP_DOCKER=1)")
    if not ensure_docker_services(PROJECT_ROOT):
        pytest.skip("Neo4j not reachable")

    cfg_dir = tmp_path_factory.mktemp("vmcfg")
    cfg_path = cfg_dir / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(FIXTURES), "ignore": FIXTURE_IGNORE},
                "vector": {
                    "enabled": True,
                    "provider": "neo4j",
                    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                },
                "graph": {
                    "enabled": True,
                    "uri": "bolt://127.0.0.1:7687",
                    "user": "neo4j",
                    "password": "vaultmemory",
                },
                "curator": {
                    "enabled": True,
                    "archive_after_days": 365,
                    "compress_after_days": 365,
                },
            }
        )
    )
    return load_config(cfg_path)


def test_services_healthy():
    assert services_healthy()


def test_full_sync_and_search(integration_config):
    sync = VaultSync(integration_config)
    try:
        health = sync.health()
        assert health["vault_exists"]
        assert health["graph"]["ok"], health["graph"]
        assert health["graph"]["vector"]["ok"]

        result = sync.run(force=True)
        assert result.indexed == fixture_note_count()
        assert not result.errors

        semantic = sync.graph.search("vector database decision", limit=3)
        assert semantic
        assert any("project-alpha" in (h.get("path") or "") for h in semantic)

        graphrag = sync.graph.search_with_graph_context("vector database", limit=2)
        assert graphrag

        neighbors = sync.graph.neighbors("project-alpha.md")
        titles = {n.get("title") for n in neighbors}
        assert "architecture-notes" in titles or "architecture-notes.md" in {
            n.get("path") for n in neighbors
        }
    finally:
        sync.close()


def test_incremental_sync_skips_unchanged(integration_config):
    sync = VaultSync(integration_config)
    try:
        sync.run(force=True)
        second = sync.run(force=False)
        assert second.skipped >= fixture_note_count()
        assert second.indexed == 0
    finally:
        sync.close()


def test_graph_delete_note(integration_config):
    sync = VaultSync(integration_config)
    try:
        sync.run(force=True)
        sync.graph.delete_note("project-alpha.md")
        rows = sync.graph.query_readonly(
            "MATCH (n:Note {path: 'project-alpha.md'}) RETURN count(n) AS c"
        )
        assert rows[0]["c"] == 0
    finally:
        sync.close()


def test_curator_dry_run_protects_fixture_notes(integration_config, tmp_path):
    state_dir = tmp_path / "curator-state"
    sync = VaultSync(integration_config, state_dir=state_dir)
    try:
        curator = VaultCurator(integration_config, state_dir=state_dir, graph=sync.graph)
        result = curator.run(dry_run=True)
        assert result.scanned == fixture_note_count()
        assert result.archived == 0
        assert result.compressed == 0
        assert result.protected >= 0
    finally:
        sync.close()


def test_mcp_tools_with_live_backends(integration_config, tmp_path, reset_server_globals):
    import vault_memory_mcp.server as srv

    state_dir = tmp_path / "mcp-state"
    os.environ["VAULT_MEMORY_CONFIG"] = str(integration_config.config_path)
    os.environ["VAULT_MEMORY_STATE_DIR"] = str(state_dir)
    srv._config = None
    srv._sync = None

    health = json.loads(srv.health_check())
    assert health["vault_exists"]
    assert health["graph"]["ok"]

    sync_result = json.loads(srv.sync_vault(force=True))
    assert sync_result["indexed"] == fixture_note_count()

    semantic = json.loads(srv.search_vault_semantic("vector database", limit=2))
    assert semantic.get("results")

    hybrid = json.loads(srv.search_vault_hybrid("vector database", limit=2))
    assert hybrid.get("results")

    neighbors = json.loads(srv.graph_neighbors("project-alpha.md"))
    assert neighbors.get("neighbors") is not None

    status = json.loads(srv.curator_status())
    assert status["enabled"] is True

    preview = json.loads(srv.run_curator(dry_run=True, force=True))
    assert preview["dry_run"] is True
    assert preview["scanned"] == fixture_note_count()

    if srv._sync:
        srv._sync.close()
        srv._sync = None


def test_provenance_graph_chain(integration_config):
    """Fact → Source → TestRun edges from note frontmatter."""
    from vault_memory_mcp.provenance import ProvenanceStore, build_research_frontmatter, write_research_note

    sync = VaultSync(integration_config)
    vault = integration_config.vault.path
    rel = "provenance-test-note.md"
    try:
        fm = build_research_frontmatter(
            source="https://example.com/provenance-test",
            source_type="test",
            confidence=0.99,
            verified_in=[
                {
                    "test_id": "provenance-chain-it",
                    "date": "2026-06-17",
                    "outcome": "success",
                    "software_version": "vault-memory test",
                    "system": "pytest",
                }
            ],
        )
        write_research_note(vault, rel, "Provenance Test", "Integration test body.", fm)
        sync.run(force=True)

        store = ProvenanceStore(sync.graph, vault)
        trail = store.provenance_trail(rel)
        assert trail["found"] is True
        assert trail["source"] == "https://example.com/provenance-test"
        assert any(t.get("outcome") == "success" for t in trail.get("tests") or [])

        rows = sync.graph.query_readonly(
            """
            MATCH (n:Note {path: $path})-[:DOCUMENTS]->(f:Fact)-[:SOURCED_FROM]->(s:Source)
            MATCH (f)-[:VERIFIED_IN]->(t:TestRun {id: 'provenance-chain-it'})
            OPTIONAL MATCH (t)-[:RAN_VERSION]->(v:Version)
            OPTIONAL MATCH (t)-[:RAN_ON]->(sys:System)
            RETURN s.url AS source, t.outcome AS outcome, v.name AS version, sys.name AS system
            """,
            {"path": rel},
        )
        assert rows, f"expected graph chain for {rel}"
        assert rows[0]["source"] == "https://example.com/provenance-test"
        assert rows[0]["outcome"] == "success"
        assert rows[0]["version"] == "vault-memory test"
        assert rows[0]["system"] == "pytest"

        from vault_memory_mcp.provenance import hybrid_search

        hybrid = hybrid_search(sync.graph, "provenance test integration", limit=3, vault_path=vault)
        assert isinstance(hybrid, list)
    finally:
        note_path = vault / rel
        if note_path.exists():
            note_path.unlink()
        sync.graph.delete_note(rel)
        sync.close()


def test_agent_memory_graph_chain(integration_config):
    """Solution + anti-pattern notes materialize concrete TestRun nodes in Neo4j."""
    from vault_memory_mcp.agent_memory import query_agent_guidance, write_agent_memory
    from vault_memory_mcp.provenance import ProvenanceStore

    sync = VaultSync(integration_config)
    vault = integration_config.vault.path
    paths: list[str] = []
    try:
        sol_rel, _, _ = write_agent_memory(
            vault,
            memory_type="solution",
            title="Neo4j Docker Cloud",
            body="Start dockerd with --storage-driver=vfs when iptables fails.",
            source="internal://cloud-agent-test",
            verified_in=[
                {
                    "test_id": "case-a-docker-vfs",
                    "date": "2026-06-17",
                    "outcome": "success",
                    "command": "dockerd --iptables=false --storage-driver=vfs",
                    "cwd": "/workspace",
                    "exit_code": 0,
                    "system": "cloud-vm",
                }
            ],
        )
        paths.append(sol_rel)

        fail_rel, _, _ = write_agent_memory(
            vault,
            memory_type="anti-pattern",
            title="Docker Default Bridge Fails",
            body="Avoid default dockerd on cloud VMs without iptables NAT support.",
            source="internal://cloud-agent-test",
            verified_in=[
                {
                    "test_id": "case-b-iptables",
                    "date": "2026-06-17",
                    "outcome": "failure",
                    "command": "dockerd",
                    "cwd": "/workspace",
                    "exit_code": 1,
                    "actual": "iptables TABLE_ADD failed",
                    "expected": "daemon running",
                    "system": "cloud-vm",
                }
            ],
        )
        paths.append(fail_rel)

        sync.run(force=True)
        store = ProvenanceStore(sync.graph, vault)

        sol_trail = store.provenance_trail(sol_rel)
        assert sol_trail["found"] is True
        assert any(t.get("outcome") == "success" for t in sol_trail.get("tests") or [])

        fail_trail = store.provenance_trail(fail_rel)
        assert fail_trail["found"] is True
        assert any(t.get("outcome") == "failure" for t in fail_trail.get("tests") or [])

        rows = sync.graph.query_readonly(
            """
            MATCH (f:Fact)-[:VERIFIED_IN]->(t:TestRun {id: 'case-a-docker-vfs'})
            RETURN t.command AS command, t.cwd AS cwd, t.exit_code AS exit_code
            """
        )
        assert rows[0]["command"] == "dockerd --iptables=false --storage-driver=vfs"
        assert rows[0]["exit_code"] == 0

        guidance = query_agent_guidance(sync.graph, vault, "docker neo4j cloud setup", limit=5)
        assert guidance["solutions"] or guidance["anti_patterns"]
    finally:
        for rel in paths:
            note_path = vault / rel
            if note_path.exists():
                note_path.unlink()
            sync.graph.delete_note(rel)
        sync.close()


def test_mcp_add_agent_memory(integration_config, tmp_path, reset_server_globals):
    import vault_memory_mcp.server as srv

    state_dir = tmp_path / "agent-mcp-state"
    os.environ["VAULT_MEMORY_CONFIG"] = str(integration_config.config_path)
    os.environ["VAULT_MEMORY_STATE_DIR"] = str(state_dir)
    srv._config = None
    srv._sync = None

    verification = json.dumps(
        [
            {
                "test_id": "mcp-agent-it",
                "date": "2026-06-17",
                "outcome": "success",
                "command": "pytest -m integration",
                "cwd": "/workspace",
                "exit_code": 0,
            }
        ]
    )
    out = json.loads(
        srv.add_agent_memory(
            title="MCP Agent Memory Test",
            body="Integration test for add_agent_memory tool.",
            memory_type="solution",
            source="internal://mcp-it",
            verification_json=verification,
        )
    )
    assert out["ok"] is True
    assert "Memory/Agent/Solutions/" in out["path"]

    guidance = json.loads(srv.query_agent_guidance("MCP agent memory", limit=3))
    assert "solutions" in guidance

    if out.get("path"):
        note_path = integration_config.vault.path / out["path"]
        if note_path.exists():
            note_path.unlink()
        if srv._sync and srv._sync.graph:
            srv._sync.graph.delete_note(out["path"])

    if srv._sync:
        srv._sync.close()
        srv._sync = None