"""Curator behavior for agent memory paths."""

from __future__ import annotations

from pathlib import Path

from vault_memory_mcp.config import load_config
from vault_memory_mcp.curator import VaultCurator
from vault_memory_mcp.obsidian import write_note


def _cfg(tmp_path: Path, vault: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f'vault:\n  path: "{vault}"\ngraph:\n  enabled: false\n'
    )
    return load_config(cfg_path)


def test_curator_protects_agent_solution(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    rel = "Memory/Agent/Solutions/docker-fix-2026-06-17.md"
    write_note(
        vault,
        rel,
        "---\ntype: solution\nstatus: success\n---\n\n# Fix\n",
    )
    curator = VaultCurator(_cfg(tmp_path, vault), state_dir=tmp_path / "state")
    result = curator.run(dry_run=True)
    protected = [a for a in result.actions if a.path == rel and a.action == "protected"]
    assert protected


def test_curator_protects_agent_anti_pattern(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    rel = "Memory/Agent/Anti-Patterns/iptables-fail-2026-06-17.md"
    write_note(
        vault,
        rel,
        "---\ntype: anti-pattern\nstatus: avoid\n---\n\n# Avoid\n",
    )
    curator = VaultCurator(_cfg(tmp_path, vault), state_dir=tmp_path / "state")
    result = curator.run(dry_run=True)
    protected = [a for a in result.actions if a.path == rel and a.action == "protected"]
    assert protected


def test_curator_lesson_not_auto_protected(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    rel = "Memory/Agent/Lessons/old-lesson-2026-06-17.md"
    write_note(
        vault,
        rel,
        "---\ntype: lesson\nstatus: active\n---\n\n# Lesson\n\nShort note.\n",
    )
    cfg = _cfg(tmp_path, vault)
    cfg.curator.archive_after_days = 0
    curator = VaultCurator(cfg, state_dir=tmp_path / "state")
    result = curator.run(dry_run=True)
    action = next(a for a in result.actions if a.path == rel)
    assert action.action != "protected"


def test_curator_dry_run_skips_vault_log(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    write_note(vault, "note.md", "# Hi\n")
    curator = VaultCurator(_cfg(tmp_path, vault), state_dir=tmp_path / "state")
    curator.run(dry_run=True)
    log_dir = vault / "Memory/Curator-Logs"
    assert not log_dir.exists() or not list(log_dir.glob("*.md"))
