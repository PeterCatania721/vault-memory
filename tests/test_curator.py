import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from vault_memory_mcp.config import load_config
from vault_memory_mcp.curator import UsageTracker, VaultCurator
from vault_memory_mcp.obsidian import read_note, write_note


def _make_config(tmp_path: Path, vault_path: Path) -> Path:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(vault_path), "ignore": []},
                "vector": {"enabled": False},
                "graph": {"enabled": False},
                "curator": {
                    "enabled": True,
                    "interval_hours": 168,
                    "stale_after_days": 1,
                    "archive_after_days": 2,
                    "compress_after_days": 1,
                    "compress_min_words": 10,
                    "compress_max_chars": 5000,
                },
            }
        )
    )
    return cfg_path


def test_protect_success_marker(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "recipe.md").write_text(
        "---\nstatus: success\n---\n\nAll tests passed. Replication steps below.\n"
    )
    cfg = load_config(_make_config(tmp_path, vault))
    curator = VaultCurator(cfg, state_dir=tmp_path / "state")
    note = read_note(vault, "recipe.md")
    action = curator.classify_note(note, state=curator.load_state(), now=datetime.now(timezone.utc))
    assert action.action == "protected"


def test_archive_stale_note(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    stale = vault / "old-session.md"
    stale.write_text("Verbose session log with no replication value.\n" * 20)
    old = time.time() - (3 * 86400)
    import os

    os.utime(stale, (old, old))

    cfg = load_config(_make_config(tmp_path, vault))
    state_dir = tmp_path / "state"
    curator = VaultCurator(cfg, state_dir=state_dir)
    result = curator.run(dry_run=False)

    assert result.archived == 1
    assert not stale.exists()
    archived = state_dir / "archive"
    assert list(archived.rglob("old-session.md"))


def test_compress_verbose_note(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note_path = vault / "verbose.md"
    body = "\n".join([f"Paragraph {i} with filler text." for i in range(200)])
    note_path.write_text(body)
    old = time.time() - (2 * 86400)
    import os

    os.utime(note_path, (old, old))

    cfg_path = tmp_path / "compress-config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(vault), "ignore": []},
                "vector": {"enabled": False},
                "graph": {"enabled": False},
                "curator": {
                    "enabled": True,
                    "stale_after_days": 1,
                    "archive_after_days": 10,
                    "compress_after_days": 1,
                    "compress_min_words": 10,
                },
            }
        )
    )
    cfg = load_config(cfg_path)
    curator = VaultCurator(cfg, state_dir=tmp_path / "state")
    result = curator.run(dry_run=False)

    assert result.compressed == 1
    compressed = read_note(vault, "verbose.md")
    assert "curator_compressed: true" in compressed.content
    assert len(compressed.content) < len(body)


def test_pin_blocks_archive(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note_path = vault / "pinned.md"
    note_path.write_text("old note\n")
    old = time.time() - (5 * 86400)
    import os

    os.utime(note_path, (old, old))

    cfg = load_config(_make_config(tmp_path, vault))
    state_dir = tmp_path / "state"
    curator = VaultCurator(cfg, state_dir=state_dir)
    curator.pin_note("pinned.md")
    result = curator.run(dry_run=False)

    assert result.protected >= 1
    assert note_path.exists()
    assert result.archived == 0


def test_usage_tracker_extends_idle_clock(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note_path = vault / "recently-used.md"
    note_path.write_text("word " * 50)
    old = time.time() - (5 * 86400)
    import os

    os.utime(note_path, (old, old))

    cfg = load_config(_make_config(tmp_path, vault))
    state_dir = tmp_path / "state"
    usage = UsageTracker(state_dir)
    usage.record("recently-used.md", action="read")

    curator = VaultCurator(cfg, state_dir=state_dir)
    note = read_note(vault, "recently-used.md")
    action = curator.classify_note(note, state=curator.load_state(), now=datetime.now(timezone.utc))
    assert action.action in {"keep", "refresh", "protected"}


def test_should_run_interval_gate(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg = load_config(_make_config(tmp_path, vault))
    curator = VaultCurator(cfg, state_dir=tmp_path / "state")
    assert curator.should_run_now() is False

    state = curator.load_state()
    state["last_run_at"] = (datetime.now(timezone.utc) - timedelta(hours=200)).isoformat()
    curator.save_state(state)
    assert curator.should_run_now() is True


def test_restore_archived_note(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    stale = vault / "restore-me.md"
    stale.write_text("temporary\n" * 30)
    old = time.time() - (4 * 86400)
    import os

    os.utime(stale, (old, old))

    cfg = load_config(_make_config(tmp_path, vault))
    state_dir = tmp_path / "state"
    curator = VaultCurator(cfg, state_dir=state_dir)
    curator.run(dry_run=False)
    restored = curator.restore_archived("restore-me.md")
    assert restored["ok"] is True
    assert (vault / "restore-me.md").exists()