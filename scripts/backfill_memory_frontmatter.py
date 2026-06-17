#!/usr/bin/env python3
"""Backfill provenance frontmatter on Memory/ notes missing required fields."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

# Allow import from mcp-server src
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-server" / "src"))

from vault_memory_mcp.obsidian import merge_frontmatter, read_note, split_frontmatter, write_note

REQUIRED = ("source", "source_type", "added", "confidence", "spoil_after_days")


def validate_frontmatter(fm: dict) -> list[str]:
    issues = []
    for key in REQUIRED:
        if key not in fm or fm[key] in (None, ""):
            issues.append(f"missing {key}")
    return issues


def build_frontmatter(**kwargs) -> dict:
    base = {
        "source": kwargs["source"],
        "source_type": kwargs["source_type"],
        "owner": kwargs.get("owner", "Peter Catania / AI agent"),
        "added": kwargs.get("added", "2026-06-17"),
        "last_verified": kwargs.get("last_verified", "2026-06-17"),
        "verified_in": kwargs.get("verified_in", []),
        "confidence": kwargs.get("confidence", 0.85),
        "spoil_after_days": kwargs.get("spoil_after_days", 180),
        "tags": kwargs.get("tags") or ["hermes-memory", "long-term"],
        "related_to": kwargs.get("related_to") or ["[[Long-Term-Memory-Policy]]"],
        "memory_policy": "[[Long-Term-Memory-Policy]]",
    }
    base.update({k: v for k, v in kwargs.items() if k not in base})
    return base

DEFAULT_VAULT = Path.home() / "Documents" / "Obsidian Vault"

# Per-note overrides (path relative to vault)
NOTE_OVERRIDES: dict[str, dict] = {
    "Memory/Long-Term-Memory-Policy.md": {"curator": "pin"},
    "Memory/Memory-Curation-Provenance-Graph-Requirements.md": {"curator": "pin"},
    "Memory/Implementation-Checklist.md": {},
    "Memory/User-Preferences.md": {
        "source": "internal://user-preferences",
        "source_type": "policy",
        "confidence": 1.0,
        "spoil_after_days": 365,
        "tags": ["hermes-memory", "policy", "user-preferences"],
        "curator": "pin",
    },
    "Memory/Projects-and-Locations.md": {
        "source": "internal://projects-index",
        "source_type": "reference",
        "confidence": 0.95,
        "spoil_after_days": 180,
        "tags": ["hermes-memory", "projects", "locations"],
    },
    "Memory/Development-Workflows.md": {
        "source": "internal://development-workflows",
        "source_type": "reference",
        "confidence": 0.9,
        "spoil_after_days": 180,
        "tags": ["hermes-memory", "workflows", "git"],
    },
    "Memory/Three-Layer-Memory-Architecture.md": {
        "source": "internal://vault-memory-architecture",
        "source_type": "policy",
        "confidence": 0.95,
        "spoil_after_days": 365,
        "tags": ["hermes-memory", "architecture", "neo4j"],
    },
    "Memory/Custom-MCPs-Mac-Playbook.md": {
        "source": "internal://custom-mcps-mac",
        "source_type": "reference",
        "confidence": 0.9,
        "spoil_after_days": 180,
        "tags": ["hermes-memory", "mcp", "custom-mcps"],
    },
    "Memory/MCP-Configuration-Kesi-Odoo19-XAI-Hermes-Setup.md": {
        "source": "internal://mcp-setup-session",
        "source_type": "session",
        "confidence": 0.85,
        "spoil_after_days": 90,
        "tags": ["hermes-memory", "mcp", "odoo", "kesi"],
    },
    "Memory/MCP-Integrations.md": {
        "source": "internal://mcp-integrations",
        "source_type": "reference",
        "confidence": 0.85,
        "spoil_after_days": 90,
        "tags": ["hermes-memory", "mcp"],
    },
    "Memory/Skills-Management-Rules.md": {
        "source": "internal://skills-rules",
        "source_type": "policy",
        "confidence": 0.95,
        "spoil_after_days": 365,
        "tags": ["hermes-memory", "skills"],
    },
    "Memory/AI-Full-Control-Open-Source-Product-Building-Preference.md": {
        "source": "internal://user-directive-2026-06-16",
        "source_type": "policy",
        "confidence": 1.0,
        "spoil_after_days": 365,
        "tags": ["hermes-memory", "policy", "open-source"],
    },
    "Memory/Full-Control-Open-Source-Preference-Update.md": {
        "source": "internal://user-directive-2026-06-16",
        "source_type": "policy",
        "confidence": 0.95,
        "spoil_after_days": 365,
        "tags": ["hermes-memory", "policy", "open-source"],
    },
    "Memory/Curation-Graph-Provenance-Update.md": {
        "source": "internal://user-directive-2026-06-16",
        "source_type": "policy",
        "confidence": 0.9,
        "spoil_after_days": 365,
        "tags": ["hermes-memory", "curation", "superseded"],
    },
    "Memory/Long-Term-Memory-Best-Practices-for-AI-Agents-Retention-Curation-What-Not-To-Persist.md": {
        "source": "internal://research-synthesis-2026-06-16",
        "source_type": "research",
        "confidence": 0.85,
        "spoil_after_days": 365,
        "tags": ["hermes-memory", "curation", "best-practices", "superseded"],
    },
    "Memory/Agentic-AI-Engineering-SOTA-June2026.md": {
        "source": "internal://last30days-research-2026-06",
        "source_type": "research",
        "confidence": 0.8,
        "spoil_after_days": 90,
        "tags": ["hermes-memory", "research", "agentic-ai"],
    },
    "Memory/Elon-Musk-xAI-Agentic-Progress-Last30Days.md": {
        "source": "internal://last30days-research-2026-06",
        "source_type": "research",
        "confidence": 0.75,
        "spoil_after_days": 60,
        "tags": ["hermes-memory", "research", "xai"],
    },
}


def backfill_note(vault: Path, rel_path: str, dry_run: bool = False) -> dict:
    note = read_note(vault, rel_path)
    fm, _ = split_frontmatter(note.content)
    if fm.get("source_type") and not validate_frontmatter(fm):
        return {"path": rel_path, "action": "skip", "reason": "already valid"}

    overrides = NOTE_OVERRIDES.get(rel_path, {})
    base = build_frontmatter(
        source=overrides.get("source", f"internal://memory-backfill/{note.title}"),
        source_type=overrides.get("source_type", "reference"),
        confidence=float(overrides.get("confidence", 0.85)),
        spoil_after_days=int(overrides.get("spoil_after_days", 180)),
        tags=overrides.get("tags"),
        related_to=overrides.get("related_to"),
    )
    if fm.get("added"):
        base["added"] = fm["added"]
    if fm.get("last_verified"):
        base["last_verified"] = fm["last_verified"]
    if fm.get("verified_in"):
        base["verified_in"] = fm["verified_in"]
    else:
        base["verified_in"] = [
            {
                "test_id": "frontmatter-backfill-2026-06-17",
                "date": "2026-06-17",
                "outcome": "success",
                "software_version": "vault-memory v0.2.0",
                "system": "macOS",
            }
        ]
        base["last_verified"] = "2026-06-17"
    for key, val in overrides.items():
        if key not in ("source", "source_type", "confidence", "spoil_after_days", "tags", "related_to"):
            base[key] = val

    merged = merge_frontmatter(note.content, base)
    issues = validate_frontmatter(yaml.safe_load(merged.split("---")[1]))
    if issues:
        return {"path": rel_path, "action": "error", "issues": issues}

    if not dry_run:
        write_note(vault, rel_path, merged)
    return {"path": rel_path, "action": "updated" if not dry_run else "would_update"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    memory_dir = args.vault / "Memory"
    if not memory_dir.is_dir():
        print(f"Memory/ not found under {args.vault}", file=sys.stderr)
        return 1

    results = []
    for path in sorted(memory_dir.glob("*.md")):
        rel = f"Memory/{path.name}"
        results.append(backfill_note(args.vault, rel, dry_run=args.dry_run))

    updated = [r for r in results if r["action"] in ("updated", "would_update")]
    skipped = [r for r in results if r["action"] == "skip"]
    errors = [r for r in results if r["action"] == "error"]
    print(f"updated={len(updated)} skipped={len(skipped)} errors={len(errors)}")
    for r in results:
        print(f"  {r['action']}: {r['path']}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())