"""Vault sync orchestrator — Neo4j-only (graph + vector embeddings)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig
from .graph import GraphStore
from .obsidian import list_notes, read_note

STATE_FILE = "sync-state.json"


@dataclass
class SyncResult:
    indexed: int
    skipped: int
    pruned: int
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "indexed": self.indexed,
            "skipped": self.skipped,
            "pruned": self.pruned,
            "errors": self.errors,
        }


class VaultSync:
    def __init__(self, config: AppConfig, state_dir: Path | None = None):
        self.config = config
        self.state_dir = state_dir or Path.home() / ".vault-memory"
        self.state_path = self.state_dir / STATE_FILE
        self.graph: GraphStore | None = None
        if config.graph.enabled:
            self.graph = GraphStore(config.graph, config.vector if config.vector.enabled else None)

    def close(self) -> None:
        if self.graph is not None:
            self.graph.close()
            self.graph = None

    def _load_state(self) -> dict[str, str]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {}

    def _save_state(self, state: dict[str, str]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2))

    def run(self, force: bool = False) -> SyncResult:
        vault = self.config.vault.path
        if not vault.exists():
            raise FileNotFoundError(f"Vault not found: {vault}")

        state = {} if force else self._load_state()
        indexed = 0
        skipped = 0
        pruned = 0
        errors: list[str] = []
        live_paths = set(list_notes(vault, self.config.vault.ignore))

        for rel in sorted(live_paths):
            try:
                note = read_note(vault, rel)
                if (
                    self.config.sync.incremental
                    and not force
                    and state.get(rel) == note.content_hash
                ):
                    skipped += 1
                    continue

                if self.graph:
                    self.graph.upsert_note(note)

                state[rel] = note.content_hash
                indexed += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{rel}: {exc}")

        orphans: set[str] = {p for p in state if p not in live_paths}
        if self.graph:
            orphans |= {p for p in self.graph.list_paths() if p not in live_paths}

        for rel in sorted(orphans):
            state.pop(rel, None)
            try:
                if self.graph:
                    self.graph.delete_note(rel)
                pruned += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"prune {rel}: {exc}")

        self._save_state(state)
        return SyncResult(indexed=indexed, skipped=skipped, pruned=pruned, errors=errors)

    def health(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "vault": str(self.config.vault.path),
            "vault_exists": self.config.vault.path.exists(),
            "store": "neo4j",
        }
        if self.graph:
            graph_health = self.graph.health()
            result["graph"] = graph_health
            # Deprecated alias for tools expecting health["vector"]
            if graph_health.get("ok") and "vector" in graph_health:
                result["vector"] = graph_health["vector"]
        return result