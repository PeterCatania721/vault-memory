"""Vault sync orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig
from .graph import GraphStore
from .obsidian import list_notes, read_note
from .vector import VectorStore

STATE_FILE = "sync-state.json"


@dataclass
class SyncResult:
    indexed: int
    skipped: int
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"indexed": self.indexed, "skipped": self.skipped, "errors": self.errors}


class VaultSync:
    def __init__(self, config: AppConfig, state_dir: Path | None = None):
        self.config = config
        self.state_dir = state_dir or Path.home() / ".vault-memory"
        self.state_path = self.state_dir / STATE_FILE
        self.vector = VectorStore(config.vector) if config.vector.enabled else None
        self.graph = GraphStore(config.graph) if config.graph.enabled else None

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
        errors: list[str] = []

        for rel in list_notes(vault, self.config.vault.ignore):
            try:
                note = read_note(vault, rel)
                if (
                    self.config.sync.incremental
                    and not force
                    and state.get(rel) == note.content_hash
                ):
                    skipped += 1
                    continue

                if self.vector:
                    self.vector.delete_note(rel)
                    self.vector.upsert_note(note)

                if self.graph and self.config.sync.wikilinks:
                    self.graph.upsert_note(note)

                state[rel] = note.content_hash
                indexed += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{rel}: {exc}")

        self._save_state(state)
        return SyncResult(indexed=indexed, skipped=skipped, errors=errors)

    def health(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "vault": str(self.config.vault.path),
            "vault_exists": self.config.vault.path.exists(),
        }
        if self.vector:
            result["vector"] = self.vector.health()
        if self.graph:
            result["graph"] = self.graph.health()
        return result