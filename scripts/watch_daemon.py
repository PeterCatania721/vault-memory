#!/usr/bin/env python3
"""Background vault watcher — incremental sync to Neo4j (vault-memory)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-server" / "src"))

os.environ.setdefault(
    "VAULT_MEMORY_CONFIG", str(Path.home() / ".vault-memory" / "config.yaml")
)

from vault_memory_mcp.config import load_config  # noqa: E402
from vault_memory_mcp.curator import VaultCurator  # noqa: E402
from vault_memory_mcp.sync import VaultSync  # noqa: E402
from watchdog.events import FileSystemEventHandler  # noqa: E402
from watchdog.observers import Observer  # noqa: E402

DEBOUNCE_SEC = 3.0
POLL_SEC = 1.0


class VaultWatchHandler(FileSystemEventHandler):
    def __init__(self) -> None:
        self._dirty = False
        self._last_event = 0.0

    def on_any_event(self, event) -> None:
        if event.is_directory:
            return
        path = str(event.src_path)
        if not path.endswith(".md"):
            return
        self._dirty = True
        self._last_event = time.time()

    def ready(self) -> bool:
        if not self._dirty:
            return False
        if time.time() - self._last_event < DEBOUNCE_SEC:
            return False
        self._dirty = False
        return True


def _maybe_curate(config, sync: VaultSync) -> None:
    curator = VaultCurator(
        config,
        state_dir=sync.state_dir,
        graph=sync.graph,
    )
    result = curator.maybe_run(dry_run=False)
    if result is None:
        return
    print(
        f"[vault-memory] curator: scanned={result.scanned} "
        f"archived={result.archived} compressed={result.compressed} "
        f"protected={result.protected}",
        flush=True,
    )


def main() -> None:
    config = load_config()
    sync = VaultSync(config)
    vault = config.vault.path

    if not vault.exists():
        raise SystemExit(f"Vault not found: {vault}")

    result = sync.run()
    print(
        f"[vault-memory] initial sync: indexed={result.indexed} "
        f"skipped={result.skipped} errors={len(result.errors)}",
        flush=True,
    )
    if result.errors:
        for err in result.errors[:5]:
            print(f"[vault-memory] error: {err}", flush=True)

    _maybe_curate(config, sync)

    handler = VaultWatchHandler()
    observer = Observer()
    observer.schedule(handler, str(vault), recursive=True)
    observer.start()
    print(f"[vault-memory] watching {vault}", flush=True)

    try:
        while True:
            if handler.ready():
                result = sync.run()
                print(
                    f"[vault-memory] sync: indexed={result.indexed} "
                    f"skipped={result.skipped} errors={len(result.errors)}",
                    flush=True,
                )
                _maybe_curate(config, sync)
            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()