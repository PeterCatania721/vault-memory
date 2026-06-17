"""Bootstrap and fallback helpers — resilient vault path resolution."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from .config import AppConfig, VaultConfig, load_config, save_config

VaultMode = Literal["user", "bootstrapped", "fixture", "missing"]

WELCOME_NOTE = """---
tags: [welcome, vault-memory]
---

# Welcome to vault-memory

This vault was auto-created by `scripts/install.sh` or bootstrap.

1. Point Obsidian here, or edit `~/.vault-memory/config.yaml` → `vault.path`
2. Run `bash scripts/docker-up.sh`
3. Call MCP `sync_vault force=true`

Agent memories live under `Memory/Agent/`. See `Memory/Three-Layer-Memory-Architecture.md` in the repo fixtures for the model.
"""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def fixture_vault_path(repo_root_path: Path | None = None) -> Path:
    root = repo_root_path or repo_root()
    return (root / "tests" / "fixtures" / "vault").resolve()


def default_bootstrap_vault() -> Path:
    return (Path.home() / ".vault-memory" / "vault").resolve()


def vault_status(cfg: AppConfig) -> dict[str, Any]:
    path = cfg.vault.path
    exists = path.exists()
    return {
        "path": str(path),
        "exists": exists,
        "is_dir": path.is_dir() if exists else False,
        "writable": os.access(path, os.W_OK) if exists else False,
    }


def bootstrap_vault_dir(path: Path, *, welcome: bool = True) -> Path:
    """Create vault directory and optional welcome note."""
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    if welcome:
        welcome_path = path / "Welcome.md"
        if not welcome_path.exists():
            welcome_path.write_text(WELCOME_NOTE, encoding="utf-8")
    return path


def _with_vault_path(cfg: AppConfig, vault_path: Path) -> AppConfig:
    return replace(cfg, vault=replace(cfg.vault, path=vault_path.resolve()))


def ensure_usable_vault(
    cfg: AppConfig,
    *,
    repo_root_path: Path | None = None,
    allow_fixture: bool = True,
    allow_bootstrap: bool = True,
) -> tuple[AppConfig, VaultMode, list[str]]:
    """Resolve a vault path that exists, or bootstrap / fall back to fixtures."""
    warnings: list[str] = []
    path = cfg.vault.path.expanduser().resolve()

    if path.exists():
        return _with_vault_path(cfg, path), "user", warnings

    bootstrap_candidates = [path, default_bootstrap_vault()]
    if allow_bootstrap:
        for candidate in bootstrap_candidates:
            try:
                bootstrap_vault_dir(candidate)
                warnings.append(f"created vault at {candidate}")
                return _with_vault_path(cfg, candidate), "bootstrapped", warnings
            except OSError as exc:
                warnings.append(f"could not create {candidate}: {exc}")

    if allow_fixture:
        fixture = fixture_vault_path(repo_root_path)
        if fixture.is_dir():
            warnings.append(f"vault missing at {path}; using repo fixtures {fixture}")
            return _with_vault_path(cfg, fixture), "fixture", warnings

    warnings.append(f"vault not found: {path}")
    return cfg, "missing", warnings


def ensure_config_and_vault(
    config_path: Path | None = None,
    *,
    repo_root_path: Path | None = None,
    allow_fixture: bool = True,
) -> tuple[AppConfig, VaultMode, list[str]]:
    """Load config then ensure vault is usable."""
    cfg = load_config(config_path)
    return ensure_usable_vault(
        cfg,
        repo_root_path=repo_root_path,
        allow_fixture=allow_fixture,
    )


def write_report_path(cfg: AppConfig, rel: str, repo_root_path: Path | None = None) -> Path:
    """Where audit/lab reports should be written."""
    if cfg.vault.path.exists():
        return cfg.vault.path / rel
    fallback = Path.home() / ".vault-memory" / "reports" / rel
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return fallback


def patch_config_vault_path(cfg: AppConfig, vault_path: Path) -> AppConfig:
    """Persist vault.path to user config when bootstrapping."""
    updated = _with_vault_path(cfg, vault_path)
    if updated.config_path.exists():
        save_config(updated)
    return updated


def recommended_vault_path_for_install() -> Path:
    return default_bootstrap_vault()
