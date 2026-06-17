#!/usr/bin/env python3
"""Elon 5-step engineering audit for vault-memory (strict order)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-server" / "src"))

os.environ.setdefault("VAULT_MEMORY_CONFIG", str(Path.home() / ".vault-memory" / "config.yaml"))

from vault_memory_mcp.config import load_config, save_config  # noqa: E402
from vault_memory_mcp.curator import VaultCurator  # noqa: E402
from vault_memory_mcp.docker_health import ensure_docker_services, services_healthy  # noqa: E402
from vault_memory_mcp.obsidian import list_notes, write_note  # noqa: E402
from vault_memory_mcp.sync import VaultSync  # noqa: E402

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def step1_requirements(cfg, sync: VaultSync) -> dict:
    """Question every requirement — delete dumb ones."""
    findings = []
    fixes = []

    raw = Path(cfg.config_path).read_text(encoding="utf-8")
    if "curator:" not in raw:
        findings.append("curator section missing from user config.yaml (relied on code defaults)")
        example = ROOT / "config" / "vault-memory.example.yaml"
        if example.exists():
            import yaml

            ex = yaml.safe_load(example.read_text()) or {}
            if "curator" in ex:
                data = yaml.safe_load(raw) or {}
                data["curator"] = ex["curator"]
                cfg.config_path.write_text(yaml.safe_dump(data, sort_keys=False))
                cfg = load_config(cfg.config_path)
                fixes.append("merged curator section from example config into ~/.vault-memory/config.yaml")

    vault_n = len(list_notes(cfg.vault.path, cfg.vault.ignore))
    graph_n = sync.health().get("graph", {}).get("notes", 0)

    hermes = cfg.vault.path / "hermes-setup.md"
    if hermes.exists() and "obsidian_notes" in hermes.read_text(encoding="utf-8"):
        findings.append("hermes-setup.md references stale collection name obsidian_notes (should be vault_memory)")

    return {
        "step": 1,
        "name": "Make Requirements Less Dumb",
        "findings": findings,
        "fixes": fixes,
        "metrics": {"vault_notes": vault_n, "graph_notes": graph_n},
        "pass": len(findings) == len(fixes) and (not findings or fixes),
    }


def step2_delete(sync: VaultSync, cfg) -> dict:
    """Delete unnecessary parts — prune orphans."""
    before_g = sync.health().get("graph", {}).get("notes", 0)
    before_v = sync.health().get("vector", {}).get("points", 0)
    vault_n = len(list_notes(cfg.vault.path, cfg.vault.ignore))
    findings = []
    if before_g > vault_n + 5:
        findings.append(f"graph bloat before prune: {before_g} nodes vs {vault_n} vault notes")

    result = sync.run(force=False)
    after_g = sync.health().get("graph", {}).get("notes", 0)
    after_v = sync.health().get("vector", {}).get("points", 0)

    return {
        "step": 2,
        "name": "Delete the Part/Process",
        "findings": findings,
        "fixes": [f"pruned {result.pruned} orphan index entries"] if result.pruned else [],
        "metrics": {
            "pruned": result.pruned,
            "graph_before": before_g,
            "graph_after": after_g,
            "vector_points_before": before_v,
            "vector_points_after": after_v,
            "vault_notes": vault_n,
        },
        "pass": after_g <= vault_n + 5 and result.pruned >= 0,
    }


def step3_simplify(cfg) -> dict:
    """Simplify what remains."""
    findings = []
    if cfg.docker.mode not in ("unified", "separate"):
        findings.append(f"unknown docker.mode={cfg.docker.mode}")
    if cfg.vector.chunk_size > 1200:
        findings.append("chunk_size > 1200 may hurt retrieval precision")

    return {
        "step": 3,
        "name": "Simplify or Optimize",
        "findings": findings,
        "fixes": [],
        "metrics": {
            "docker_mode": cfg.docker.mode,
            "chunk_size": cfg.vector.chunk_size,
            "embedding": cfg.vector.embedding_model,
        },
        "pass": not findings,
    }


def step4_accelerate() -> dict:
    """Accelerate cycle time — fast test loop."""
    t0 = datetime.now(timezone.utc)
    proc = subprocess.run(
        ["uv", "run", "pytest", "-q", str(ROOT / "tests"), "-m", "not integration", "--tb=no"],
        cwd=ROOT / "mcp-server",
        capture_output=True,
        text=True,
        timeout=120,
    )
    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
    passed = proc.returncode == 0
    return {
        "step": 4,
        "name": "Accelerate Cycle Time",
        "findings": [] if passed else [proc.stdout[-500:]],
        "fixes": [],
        "metrics": {"unit_test_seconds": round(elapsed, 2), "unit_tests_pass": passed},
        "pass": passed,
    }


def step5_automate(sync: VaultSync, cfg) -> dict:
    """Automate only after 1-4."""
    curator = VaultCurator(cfg, state_dir=sync.state_dir, graph=sync.graph)
    findings = []
    fixes = []

    if not services_healthy():
        ensure_docker_services(ROOT)
    if not services_healthy():
        findings.append("Qdrant/Neo4j not healthy — automation cannot run")

    preview = curator.run(dry_run=True)
    lab_protected = all(
        a.action != "archive" for a in preview.actions if "vault-memory-lab" in a.path
    )
    if not lab_protected:
        findings.append("curator dry-run would archive lab playbooks")

    status = curator.status()
    if status.get("pinned_count", 0) < 1:
        findings.append("no pinned umbrella playbook")
    else:
        fixes.append(f"pinned: {status.get('pinned')}")

    auto_scripts = [
        ROOT / "scripts" / "test-cycle.sh",
        ROOT / "scripts" / "watch_daemon.py",
        ROOT / "scripts" / "vault-memory-lab.py",
        ROOT / "scripts" / "elon-5step-audit.py",
    ]
    missing = [str(p.name) for p in auto_scripts if not p.exists()]
    if missing:
        findings.append(f"missing automation scripts: {missing}")

    return {
        "step": 5,
        "name": "Automate",
        "findings": findings,
        "fixes": fixes,
        "metrics": {
            "curator_enabled": status.get("enabled"),
            "lab_protected": lab_protected,
            "automation_scripts": len(auto_scripts) - len(missing),
        },
        "pass": not findings,
    }


def write_report(cfg, steps: list[dict]) -> Path:
    report_dir = cfg.vault.path / "vault-memory-lab"
    report_dir.mkdir(parents=True, exist_ok=True)
    rel = "vault-memory-lab/elon-5step-audit.md"
    lines = [
        "---",
        "status: success",
        "type: playbook",
        "vault-memory: protected",
        "tags: [test-success, playbook, elon-5step, replicable]",
        f"verified_at: {NOW}",
        "---",
        "",
        "# Elon 5-Step Audit — vault-memory",
        "",
        f"Run at: {NOW}",
        "",
    ]
    all_pass = all(s["pass"] for s in steps)
    lines.append(f"**Overall:** {'PASS' if all_pass else 'NEEDS ATTENTION'}")
    lines.append("")
    for s in steps:
        icon = "✅" if s["pass"] else "⚠️"
        lines.append(f"## Step {s['step']}: {s['name']} {icon}")
        if s.get("findings"):
            lines.append("**Findings:**")
            for f in s["findings"]:
                lines.append(f"- {f}")
        if s.get("fixes"):
            lines.append("**Fixes applied:**")
            for f in s["fixes"]:
                lines.append(f"- {f}")
        lines.append(f"**Metrics:** `{json.dumps(s.get('metrics', {}))}`")
        lines.append("")
    write_note(cfg.vault.path, rel, "\n".join(lines) + "\n")
    return cfg.vault.path / rel


def main() -> int:
    cfg = load_config()
    sync = VaultSync(cfg)
    steps = []
    for fn, args in (
        (step1_requirements, (cfg, sync)),
        (step2_delete, (sync, cfg)),
        (step3_simplify, (load_config(),)),
        (step4_accelerate, ()),
        (step5_automate, (sync, load_config())),
    ):
        steps.append(fn(*args))
        print(f"step {steps[-1]['step']} done: pass={steps[-1]['pass']}", flush=True)
    report = write_report(load_config(), steps)
    sync.run(force=False)

    out = {"at": NOW, "all_pass": all(s["pass"] for s in steps), "steps": steps, "report": str(report)}
    log = Path.home() / ".vault-memory" / "logs" / "elon"
    log.mkdir(parents=True, exist_ok=True)
    (log / f"audit-{NOW.replace(':', '-')}.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0 if out["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())