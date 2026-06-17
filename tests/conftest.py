"""Shared fixtures for vault-memory tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from vault_memory_mcp.config import load_config

FIXTURES = Path(__file__).parent / "fixtures" / "vault"
FIXTURE_IGNORE = ["Memory/Curator-Logs/**", "**/provenance-test-note.md"]
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fixture_note_count() -> int:
    from vault_memory_mcp.obsidian import list_notes

    return len(list_notes(FIXTURES, FIXTURE_IGNORE))


@pytest.fixture
def fixtures_vault() -> Path:
    return FIXTURES


@pytest.fixture
def isolated_config(tmp_path: Path, fixtures_vault: Path) -> Path:
    """Minimal config pointing at fixture vault, DBs disabled."""
    cfg_path = tmp_path / "config.yaml"
    state_dir = tmp_path / "state"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(fixtures_vault), "ignore": FIXTURE_IGNORE},
                "vector": {"enabled": False},
                "graph": {"enabled": False},
                "curator": {"enabled": True, "interval_hours": 168},
            }
        )
    )
    os.environ["VAULT_MEMORY_CONFIG"] = str(cfg_path)
    os.environ["VAULT_MEMORY_STATE_DIR"] = str(state_dir)
    yield cfg_path
    os.environ.pop("VAULT_MEMORY_STATE_DIR", None)


@pytest.fixture
def reset_server_globals():
    """Reset MCP server module-level caches between tests."""
    import vault_memory_mcp.server as srv

    old_config = srv._config
    old_sync = srv._sync
    srv._config = None
    srv._sync = None
    yield
    srv._config = old_config
    srv._sync = old_sync