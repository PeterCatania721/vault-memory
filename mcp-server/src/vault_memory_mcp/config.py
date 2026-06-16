"""Load and validate vault-memory YAML configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path.home() / ".vault-memory" / "config.yaml"


@dataclass
class VaultConfig:
    path: Path
    ignore: list[str] = field(default_factory=lambda: [".obsidian/**", ".trash/**"])


@dataclass
class VectorConfig:
    enabled: bool = True
    provider: str = "qdrant"
    url: str = "http://127.0.0.1:6333"
    collection: str = "vault_memory"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 800
    chunk_overlap: int = 100


@dataclass
class GraphConfig:
    enabled: bool = True
    provider: str = "neo4j"
    uri: str = "bolt://127.0.0.1:7687"
    user: str = "neo4j"
    password: str = "vaultmemory"
    database: str = "neo4j"


@dataclass
class SyncConfig:
    wikilinks: bool = True
    incremental: bool = True


@dataclass
class DockerConfig:
    mode: str = "unified"


@dataclass
class AppConfig:
    vault: VaultConfig
    vector: VectorConfig = field(default_factory=VectorConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    config_path: Path = field(default_factory=lambda: DEFAULT_CONFIG_PATH)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vault": {
                "path": str(self.vault.path),
                "ignore": self.vault.ignore,
            },
            "vector": {
                "enabled": self.vector.enabled,
                "provider": self.vector.provider,
                "url": self.vector.url,
                "collection": self.vector.collection,
                "embedding_model": self.vector.embedding_model,
                "chunk_size": self.vector.chunk_size,
                "chunk_overlap": self.vector.chunk_overlap,
            },
            "graph": {
                "enabled": self.graph.enabled,
                "provider": self.graph.provider,
                "uri": self.graph.uri,
                "user": self.graph.user,
                "password": self.graph.password,
                "database": self.graph.database,
            },
            "sync": {
                "wikilinks": self.sync.wikilinks,
                "incremental": self.sync.incremental,
            },
            "docker": {"mode": self.docker.mode},
        }


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or Path(
        os.environ.get("VAULT_MEMORY_CONFIG", DEFAULT_CONFIG_PATH)
    )
    if not config_path.exists():
        example = Path(__file__).resolve().parents[3] / "config" / "vault-memory.example.yaml"
        if example.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(example.read_text())
        else:
            raise FileNotFoundError(
                f"No config at {config_path}. Copy config/vault-memory.example.yaml first."
            )

    raw = yaml.safe_load(config_path.read_text()) or {}
    vault_raw = raw.get("vault", {})
    vector_raw = raw.get("vector", {})
    graph_raw = raw.get("graph", {})
    sync_raw = raw.get("sync", {})
    docker_raw = raw.get("docker", {})

    return AppConfig(
        vault=VaultConfig(
            path=_expand(vault_raw.get("path", "~/Documents/Obsidian/MyVault")),
            ignore=vault_raw.get("ignore", [".obsidian/**", ".trash/**"]),
        ),
        vector=VectorConfig(**{k: v for k, v in vector_raw.items() if k in VectorConfig.__dataclass_fields__}),
        graph=GraphConfig(**{k: v for k, v in graph_raw.items() if k in GraphConfig.__dataclass_fields__}),
        sync=SyncConfig(**{k: v for k, v in sync_raw.items() if k in SyncConfig.__dataclass_fields__}),
        docker=DockerConfig(**{k: v for k, v in docker_raw.items() if k in DockerConfig.__dataclass_fields__}),
        config_path=config_path,
    )


def save_config(config: AppConfig) -> None:
    config.config_path.parent.mkdir(parents=True, exist_ok=True)
    config.config_path.write_text(yaml.safe_dump(config.to_dict(), sort_keys=False))