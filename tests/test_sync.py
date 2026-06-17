"""Unit tests for VaultSync orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from vault_memory_mcp.config import load_config
from vault_memory_mcp.sync import VaultSync

from conftest import FIXTURE_IGNORE, FIXTURES, fixture_note_count


def test_sync_indexes_all_notes(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    state_dir = tmp_path / "state"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(FIXTURES), "ignore": FIXTURE_IGNORE},
                "vector": {"enabled": False},
                "graph": {"enabled": False},
            }
        )
    )
    cfg = load_config(cfg_path)
    sync = VaultSync(cfg, state_dir=state_dir)
    result = sync.run(force=True)
    assert result.indexed == fixture_note_count()
    assert not result.errors
    assert sync.state_path.exists()


def test_sync_incremental_skip(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(FIXTURES), "ignore": FIXTURE_IGNORE},
                "vector": {"enabled": False},
                "graph": {"enabled": False},
                "sync": {"incremental": True},
            }
        )
    )
    cfg = load_config(cfg_path)
    sync = VaultSync(cfg, state_dir=tmp_path / "state")
    sync.run(force=True)
    second = sync.run(force=False)
    assert second.skipped == fixture_note_count()
    assert second.indexed == 0


def test_sync_prunes_orphan_index_entries(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    vault = tmp_path / "vault"
    vault.mkdir()
    keep = vault / "keep.md"
    drop = vault / "drop.md"
    keep.write_text("keep\n")
    drop.write_text("drop\n")

    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(vault), "ignore": []},
                "vector": {"enabled": False},
                "graph": {"enabled": False},
            }
        )
    )
    cfg = load_config(cfg_path)
    state_dir = tmp_path / "state"
    sync = VaultSync(cfg, state_dir=state_dir)
    sync.run(force=True)
    drop.unlink()
    result = sync.run(force=False)
    assert result.pruned >= 1
    state = json.loads((state_dir / "sync-state.json").read_text())
    assert "drop.md" not in state
    assert "keep.md" in state


def test_health_reports_vault(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump({"vault": {"path": str(FIXTURES), "ignore": []}, "vector": {"enabled": False}, "graph": {"enabled": False}})
    )
    cfg = load_config(cfg_path)
    health = VaultSync(cfg).health()
    assert health["vault_exists"] is True