"""Plugin structure and environment validation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.environment

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "rel",
    [
        ".mcp.json",
        ".grok-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        "hooks/hooks.json",
        "config/vault-memory.example.yaml",
        "scripts/install.sh",
        "scripts/test-cycle.sh",
        "scripts/docker-up.sh",
        "scripts/curator-run.sh",
        "scripts/watch_daemon.py",
        "skills/vault-memory-setup/SKILL.md",
        "skills/vault-memory-sync/SKILL.md",
        "skills/vault-memory-query/SKILL.md",
        "skills/vault-memory-curator/SKILL.md",
        "commands/vault-sync.md",
        "commands/vault-curate.md",
    ],
)
def test_required_plugin_files_exist(rel: str):
    assert (ROOT / rel).exists(), f"missing {rel}"


def test_mcp_json_points_at_mcp_server():
    data = json.loads((ROOT / ".mcp.json").read_text())
    srv = data["mcpServers"]["vault-memory"]
    args = srv["args"]
    assert srv["command"] == "uv"
    assert "run" in args
    assert "vault-memory-mcp" in args
    assert any("mcp-server" in str(a) for a in args)


def test_example_config_has_curator_section():
    raw = yaml.safe_load((ROOT / "config/vault-memory.example.yaml").read_text())
    assert "curator" in raw
    assert raw["curator"]["enabled"] is True


def test_hooks_session_start_async():
    hooks = json.loads((ROOT / "hooks/hooks.json").read_text())
    startup = hooks["hooks"]["SessionStart"][0]["hooks"][0]
    assert startup["async"] is True
    assert "session-check.sh" in startup["command"]


def test_scripts_are_executable():
    for name in ("install.sh", "test-cycle.sh", "docker-up.sh", "curator-run.sh", "session-check.sh"):
        path = ROOT / "scripts" / name
        assert path.stat().st_mode & 0o111, f"{name} should be executable"


def test_mcp_server_imports():
    subprocess.run(
        [
            "uv",
            "run",
            "--directory",
            str(ROOT / "mcp-server"),
            "python",
            "-c",
            "from vault_memory_mcp.server import mcp; assert mcp.name == 'vault-memory'",
        ],
        check=True,
        cwd=ROOT,
    )


def test_plugin_version_consistent():
    grok = json.loads((ROOT / ".grok-plugin/plugin.json").read_text())
    claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert grok["version"] == claude["version"]
    import tomllib

    pyproject = tomllib.loads((ROOT / "mcp-server/pyproject.toml").read_text())
    pkg_version = pyproject["project"]["version"]
    assert grok["version"] == pkg_version
    from vault_memory_mcp import __version__

    assert __version__ == pkg_version