#!/usr/bin/env python3
"""CLI wrapper for add_research_memory — provenance-structured vault notes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "mcp-server"
sys.path.insert(0, str(ROOT / "src"))

from vault_memory_mcp.config import load_config
from vault_memory_mcp.graph import GraphStore
from vault_memory_mcp.provenance import (
    ProvenanceStore,
    build_research_frontmatter,
    validate_frontmatter,
    write_research_note,
)
from vault_memory_mcp.sync import VaultSync


def main() -> int:
    parser = argparse.ArgumentParser(description="Add provenance-structured research memory note")
    parser.add_argument("topic", help="Research topic title")
    parser.add_argument("--body-file", required=True, help="Markdown body file")
    parser.add_argument("--source", required=True, help="Primary source URL or identifier")
    parser.add_argument("--source-type", default="research")
    parser.add_argument("--confidence", type=float, default=0.85)
    parser.add_argument("--spoil-days", type=int, default=180)
    parser.add_argument("--verification", default="[]", help="JSON list of verified_in entries")
    args = parser.parse_args()

    cfg = load_config()
    body = Path(args.body_file).read_text(encoding="utf-8")
    verified = json.loads(args.verification)
    fm = build_research_frontmatter(
        source=args.source,
        source_type=args.source_type,
        confidence=args.confidence,
        spoil_after_days=args.spoil_days,
        verified_in=verified,
    )
    issues = validate_frontmatter(fm, memory_note=True)
    if issues:
        print(json.dumps({"ok": False, "issues": issues}, indent=2))
        return 1

    day = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
    slug = args.topic.lower().replace(" ", "-")[:60]
    rel = f"Memory/Research-{slug}-{day}.md"
    write_research_note(cfg.vault.path, rel, args.topic, body, fm)

    sync = VaultSync(cfg)
    try:
        if sync.graph:
            store = ProvenanceStore(sync.graph, cfg.vault.path)
            prov = store.upsert_from_note(rel)
            sync.run(force=False)
        else:
            prov = {"ok": False, "reason": "graph disabled"}
        print(json.dumps({"ok": True, "path": rel, "provenance": prov}, indent=2))
        return 0
    finally:
        sync.close()


if __name__ == "__main__":
    raise SystemExit(main())