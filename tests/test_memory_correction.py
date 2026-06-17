"""Tests for invalid/expiry deletion and memory correction."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from vault_memory_mcp.config import load_config
from vault_memory_mcp.curator import VaultCurator
from vault_memory_mcp.obsidian import list_notes, read_note, write_note
from vault_memory_mcp.sync import VaultSync


def _cfg(tmp_path: Path, vault: Path) -> Path:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(vault), "ignore": []},
                "vector": {"enabled": False},
                "graph": {"enabled": False},
                "curator": {
                    "archive_after_days": 365,
                    "compress_after_days": 365,
                },
            }
        )
    )
    return cfg_path


def test_mark_invalid_archived_by_curator(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    rel = "false-claim.md"
    write_note(vault, rel, "# Wrong\n\nPort 9999 is correct.\n")
    cfg = load_config(_cfg(tmp_path, vault))
    curator = VaultCurator(cfg, state_dir=tmp_path / "state")
    curator.mark_invalid(rel, reason="validated false in test")
    result = curator.run(dry_run=False)
    assert result.archived == 1
    assert rel not in list_notes(vault)


def test_expired_note_archived(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    rel = "expired.md"
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    write_note(
        vault,
        rel,
        f"---\nexpires_at: {yesterday}\n---\n\nOld data.\n",
    )
    cfg = load_config(_cfg(tmp_path, vault))
    curator = VaultCurator(cfg, state_dir=tmp_path / "state")
    result = curator.run(dry_run=False)
    assert result.archived == 1
    assert rel not in list_notes(vault)


def test_delete_note_archives_and_purges_state(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    rel = "drop-me.md"
    write_note(vault, rel, "temporary\n")
    cfg = load_config(_cfg(tmp_path, vault))
    state_dir = tmp_path / "state"
    curator = VaultCurator(cfg, state_dir=state_dir)
    out = curator.delete_note(rel)
    assert out["ok"] is True
    assert rel not in list_notes(vault)
    assert not (vault / rel).exists()