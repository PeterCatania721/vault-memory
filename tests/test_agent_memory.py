"""Tests for agentic memory layer (concrete Neo4j + abstract Obsidian)."""

from __future__ import annotations

from vault_memory_mcp.agent_memory import (
    build_agent_frontmatter,
    query_agent_guidance,
    rank_agent_hit,
    validate_verified_in_entry,
    write_agent_memory,
)


def test_build_agent_frontmatter_solution():
    fm = build_agent_frontmatter(
        memory_type="solution",
        source="internal://test-run",
        verified_in=[
            {
                "test_id": "case-a-pass",
                "date": "2026-06-17",
                "outcome": "success",
                "command": "pytest -q",
                "cwd": "/workspace",
                "exit_code": 0,
            }
        ],
    )
    assert fm["type"] == "solution"
    assert fm["status"] == "success"
    assert fm["abstraction_layer"] == "abstract"
    assert "test-success" in fm["tags"]


def test_build_agent_frontmatter_anti_pattern():
    fm = build_agent_frontmatter(
        memory_type="anti-pattern",
        source="internal://failed-attempt",
        verified_in=[
            {
                "test_id": "case-b-fail",
                "date": "2026-06-17",
                "outcome": "failure",
                "command": "docker compose up",
                "cwd": "/workspace",
                "exit_code": 1,
                "actual": "iptables failed",
            }
        ],
    )
    assert fm["type"] == "anti-pattern"
    assert fm["status"] == "avoid"
    assert "avoid" in fm["tags"]


def test_validate_verified_in_entry_requires_recreation_fields():
    issues = validate_verified_in_entry(
        {
            "test_id": "t1",
            "date": "2026-06-17",
            "outcome": "success",
            "command": "bash scripts/test-cycle.sh",
            "cwd": "/workspace",
            "exit_code": 0,
        }
    )
    assert not issues


def test_validate_verified_in_bad_outcome():
    issues = validate_verified_in_entry(
        {"test_id": "t1", "date": "2026-06-17", "outcome": "maybe"}
    )
    assert any("outcome" in i for i in issues)


def test_rank_agent_hit_boosts_success():
    fm_success = {
        "type": "solution",
        "status": "success",
        "confidence": 0.9,
        "verified_in": [{"outcome": "success", "test_id": "t1", "date": "2026-06-17"}],
    }
    fm_failure = {
        "type": "anti-pattern",
        "status": "avoid",
        "verified_in": [{"outcome": "failure", "test_id": "t2", "date": "2026-06-17"}],
    }
    hit = {"score": 0.7}
    assert rank_agent_hit(hit, fm_success) > rank_agent_hit(hit, fm_failure)


def test_validate_agent_verified_in_requires_recreation():
    from vault_memory_mcp.agent_memory import validate_agent_verified_in

    issues = validate_agent_verified_in(
        "solution",
        [{"test_id": "t1", "date": "2026-06-17", "outcome": "success"}],
    )
    assert any("command" in i for i in issues)


def test_write_agent_memory_rejects_missing_recreation(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    rel, _, issues = write_agent_memory(
        vault,
        memory_type="solution",
        title="Incomplete",
        body="Missing recreation metadata.",
        source="internal://test",
        verified_in=[],
    )
    assert rel == ""
    assert issues
    assert not list(vault.rglob("*.md"))


def test_write_agent_memory_paths(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    rel, fm, issues = write_agent_memory(
        vault,
        memory_type="solution",
        title="Docker Neo4j Setup",
        body="Use vfs storage driver when iptables unavailable.",
        source="internal://cloud-test",
        verified_in=[
            {
                "test_id": "docker-vfs",
                "date": "2026-06-17",
                "outcome": "success",
                "command": "dockerd --storage-driver=vfs",
                "cwd": "/workspace",
                "exit_code": 0,
            }
        ],
    )
    assert rel.startswith("Memory/Agent/Solutions/")
    assert not issues
    assert (vault / rel).exists()
    assert fm["type"] == "solution"


def test_query_agent_guidance_empty_graph(tmp_path):
    """query_agent_guidance returns structure even with no hits."""
    from unittest.mock import MagicMock

    graph = MagicMock()
    graph.search_with_graph_context = MagicMock(return_value=[])
    graph.query_readonly = MagicMock(return_value=[])
    graph.vector = None
    vault = tmp_path / "vault"
    vault.mkdir()

    result = query_agent_guidance(graph, vault, "docker neo4j setup", limit=3)
    assert result["query"] == "docker neo4j setup"
    assert "solutions" in result
    assert "anti_patterns" in result
    assert "lessons" in result
