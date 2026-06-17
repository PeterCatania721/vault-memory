"""MCP handler tests for agent memory — common error paths."""

from __future__ import annotations

import json

import pytest

import vault_memory_mcp.server as srv


@pytest.fixture(autouse=True)
def _server_env(isolated_config, reset_server_globals):
    srv._config = None
    srv._sync = None
    yield
    srv._config = None
    srv._sync = None


def test_add_agent_memory_rejects_missing_recreation():
    out = json.loads(
        srv.add_agent_memory(
            title="Bad solution",
            body="No command recorded.",
            memory_type="solution",
            source="internal://test",
            verification_json="[]",
        )
    )
    assert out["ok"] is False
    assert out.get("issues")


def test_add_agent_memory_rejects_invalid_memory_type():
    out = json.loads(
        srv.add_agent_memory(
            title="Nope",
            body="body",
            memory_type="guess",
            source="internal://test",
        )
    )
    assert out["ok"] is False
    assert "error" in out or "issues" in out


def test_add_agent_memory_rejects_wrong_outcome_for_anti_pattern():
    out = json.loads(
        srv.add_agent_memory(
            title="False anti-pattern",
            body="Marked failure but outcome success.",
            memory_type="anti-pattern",
            source="internal://test",
            verification_json=json.dumps(
                [
                    {
                        "test_id": "case-x",
                        "date": "2026-06-17",
                        "outcome": "success",
                        "command": "false",
                        "cwd": "/tmp",
                        "exit_code": 0,
                    }
                ]
            ),
        )
    )
    assert out["ok"] is False


def test_query_agent_guidance_graph_disabled(isolated_config):
    out = json.loads(srv.query_agent_guidance("docker setup"))
    assert "error" in out


def test_query_agent_guidance_returns_buckets_structure(isolated_config):
    """Structure is valid even when graph disabled — error path."""
    out = json.loads(srv.query_agent_guidance("test"))
    assert isinstance(out, dict)


def test_get_config_no_deprecated_vector_fields(isolated_config):
    cfg = json.loads(srv.get_config())
    vector = cfg["vector"]
    assert "url" not in vector
    assert "collection" not in vector


def test_search_vault_graphrag_removed():
    assert not hasattr(srv, "search_vault_graphrag")


def test_mcp_exposes_query_agent_guidance_not_tool_suffix():
    assert hasattr(srv, "query_agent_guidance")
    assert not hasattr(srv, "query_agent_guidance_tool")
