"""Unit tests for MCP server tool handlers."""

from __future__ import annotations

import json
import os

import pytest

import vault_memory_mcp.server as srv

from conftest import fixture_note_count


@pytest.fixture(autouse=True)
def _server_env(isolated_config, reset_server_globals):
    srv._config = None
    srv._sync = None
    yield
    srv._config = None
    srv._sync = None


def test_health_check_local(isolated_config):
    data = json.loads(srv.health_check())
    assert data["vault_exists"] is True
    assert "vector" not in data or data.get("vector") is None


def test_get_config_includes_curator(isolated_config):
    data = json.loads(srv.get_config())
    assert "curator" in data
    assert data["curator"]["enabled"] is True


def test_list_and_read_notes(isolated_config):
    listing = json.loads(srv.list_vault_notes())
    assert listing["count"] == fixture_note_count()
    assert "project-alpha.md" in listing["notes"]

    note = json.loads(srv.read_vault_note("project-alpha.md"))
    assert note["title"] == "project-alpha"
    assert "architecture-notes" in note["wikilinks"]


def test_search_vault_keyword(isolated_config):
    hits = json.loads(srv.search_vault_keyword("Neo4j", limit=5))
    assert hits["results"]
    assert hits["results"][0]["path"] == "project-alpha.md"


def test_search_semantic_disabled(isolated_config):
    out = json.loads(srv.search_vault_semantic("anything"))
    assert "error" in out


def test_sync_vault_local(isolated_config):
    result = json.loads(srv.sync_vault(force=True))
    assert result["indexed"] == fixture_note_count()
    assert not result["errors"]


def test_curator_status_and_pin(isolated_config):
    status = json.loads(srv.curator_status())
    assert status["enabled"] is True
    assert status["pinned"] == []

    pin = json.loads(srv.curator_pin("project-alpha.md"))
    assert pin["ok"] is True

    status2 = json.loads(srv.curator_status())
    assert "project-alpha.md" in status2["pinned"]

    unpin = json.loads(srv.curator_unpin("project-alpha.md"))
    assert unpin["ok"] is True


def test_run_curator_force_dry_run(isolated_config):
    result = json.loads(srv.run_curator(dry_run=True, force=True))
    assert result["dry_run"] is True
    assert result["scanned"] == fixture_note_count()


def test_update_config_curator_threshold(isolated_config):
    out = json.loads(
        srv.update_config(json.dumps({"curator": {"archive_after_days": 120}}))
    )
    assert out["ok"] is True
    cfg = json.loads(srv.get_config())
    assert cfg["curator"]["archive_after_days"] == 120


def test_read_records_usage(isolated_config):
    state_dir = os.environ["VAULT_MEMORY_STATE_DIR"]
    srv.read_vault_note("project-alpha.md")
    usage_path = os.path.join(state_dir, "usage-state.json")
    assert os.path.exists(usage_path)
    data = json.loads(open(usage_path, encoding="utf-8").read())
    assert "project-alpha.md" in data.get("notes", {})