"""Elon audit script runs without a preconfigured Obsidian vault."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import PROJECT_ROOT

ROOT = PROJECT_ROOT


@pytest.mark.environment
def test_elon_audit_runs_with_fixture_fallback(tmp_path: Path):
    cfg_dir = tmp_path / "vmcfg"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(tmp_path / "nonexistent-obsidian-vault")},
                "vector": {"enabled": False},
                "graph": {"enabled": False},
            }
        )
    )
    env = {
        **dict(__import__("os").environ),
        "VAULT_MEMORY_CONFIG": str(cfg_path),
        "VAULT_MEMORY_AUDIT_SKIP_TESTS": "1",
        "PATH": __import__("os").environ.get("PATH", ""),
    }
    proc = subprocess.run(
        ["uv", "run", "python", str(ROOT / "scripts" / "elon-5step-audit.py")],
        cwd=ROOT / "mcp-server",
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    match = re.search(r'\{\s*"at":.*\}\s*$', proc.stdout, re.DOTALL)
    assert match, proc.stdout[-500:]
    data = json.loads(match.group(0))
    assert data["vault_mode"] in ("fixture", "bootstrapped", "user")
    assert data["all_pass"] is True
