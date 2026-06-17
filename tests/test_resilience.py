"""Resilience helpers — vault bootstrap and fallback."""

from __future__ import annotations

from pathlib import Path

import yaml

from vault_memory_mcp.config import load_config
from vault_memory_mcp.resilience import (
    bootstrap_vault_dir,
    ensure_usable_vault,
    fixture_vault_path,
)
from vault_memory_mcp.sync import VaultSync

from conftest import PROJECT_ROOT


def test_bootstrap_vault_creates_welcome(tmp_path: Path):
    vault = tmp_path / "new-vault"
    bootstrap_vault_dir(vault)
    assert vault.exists()
    assert (vault / "Welcome.md").exists()


def test_ensure_usable_vault_bootstraps_missing(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    vault = tmp_path / "vault"
    cfg_path.write_text(yaml.safe_dump({"vault": {"path": str(vault)}}))
    cfg = load_config(cfg_path)
    cfg, mode, _ = ensure_usable_vault(cfg, allow_fixture=False)
    assert mode == "bootstrapped"
    assert cfg.vault.path.exists()


def test_ensure_usable_vault_fixture_fallback(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    missing = tmp_path / "no-such-vault"
    cfg_path.write_text(yaml.safe_dump({"vault": {"path": str(missing)}}))
    cfg = load_config(cfg_path)
    cfg, mode, warnings = ensure_usable_vault(
        cfg, repo_root_path=PROJECT_ROOT, allow_bootstrap=False, allow_fixture=True
    )
    assert mode == "fixture"
    assert cfg.vault.path == fixture_vault_path(PROJECT_ROOT)
    assert warnings


def test_sync_run_soft_fail_without_vault(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(tmp_path / "missing")},
                "graph": {"enabled": False},
                "vector": {"enabled": False},
            }
        )
    )
    cfg = load_config(cfg_path)
    sync = VaultSync(cfg, state_dir=tmp_path / "state")
    result = sync.run(require_vault=False)
    assert result.indexed == 0
    assert result.errors
    sync.close()


def test_health_includes_hint_when_vault_missing(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump({"vault": {"path": str(tmp_path / "nope")}}))
    cfg = load_config(cfg_path)
    sync = VaultSync(cfg, state_dir=tmp_path / "state")
    health = sync.health()
    assert health["vault_exists"] is False
    assert "hint" in health
    sync.close()
