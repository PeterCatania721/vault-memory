from pathlib import Path

import yaml

from vault_memory_mcp.config import load_config, save_config


def test_load_save_roundtrip(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    fixture_vault = Path(__file__).parent / "fixtures" / "vault"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "vault": {"path": str(fixture_vault), "ignore": []},
                "vector": {"enabled": False},
                "graph": {"enabled": False},
            }
        )
    )
    cfg = load_config(cfg_path)
    assert cfg.vault.path == fixture_vault.resolve()
    save_config(cfg)
    reloaded = load_config(cfg_path)
    assert reloaded.vault.path == fixture_vault.resolve()


def test_curator_config_defaults(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    fixture_vault = Path(__file__).parent / "fixtures" / "vault"
    cfg_path.write_text(
        yaml.safe_dump({"vault": {"path": str(fixture_vault)}})
    )
    cfg = load_config(cfg_path)
    assert cfg.curator.enabled is True
    assert cfg.curator.interval_hours == 168
    assert "playbooks/**" in cfg.curator.protect_paths