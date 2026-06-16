"""Integration tests — require Docker (pytest -m integration)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from vault_memory_mcp.config import load_config
from vault_memory_mcp.sync import VaultSync

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parent / "fixtures" / "vault"


def _docker_up() -> bool:
    import subprocess

    root = Path(__file__).resolve().parents[1]
    try:
        subprocess.run(
            ["bash", str(root / "scripts" / "docker-up.sh")],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def integration_config(tmp_path_factory):
    if os.environ.get("VAULT_MEMORY_SKIP_DOCKER") == "1":
        pytest.skip("Docker integration skipped")
    if not _docker_up():
        pytest.skip("Docker not available")

    cfg_dir = tmp_path_factory.mktemp("vmcfg")
    cfg_path = cfg_dir / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(FIXTURES), "ignore": []},
                "vector": {
                    "enabled": True,
                    "url": "http://127.0.0.1:6333",
                    "collection": "vault_memory_test",
                },
                "graph": {
                    "enabled": True,
                    "uri": "bolt://127.0.0.1:7687",
                    "user": "neo4j",
                    "password": "vaultmemory",
                },
            }
        )
    )
    return load_config(cfg_path)


def test_full_sync_and_search(integration_config):
    sync = VaultSync(integration_config)
    health = sync.health()
    assert health["vault_exists"]
    assert health["vector"]["ok"], health["vector"]
    assert health["graph"]["ok"], health["graph"]

    result = sync.run(force=True)
    assert result.indexed == 2
    assert not result.errors

    semantic = sync.vector.search("vector database decision", limit=3)
    assert semantic
    assert any("project-alpha" in (h.get("path") or "") for h in semantic)

    neighbors = sync.graph.neighbors("project-alpha.md")
    titles = {n.get("title") for n in neighbors}
    assert "architecture-notes" in titles or "architecture-notes.md" in {
        n.get("path") for n in neighbors
    }