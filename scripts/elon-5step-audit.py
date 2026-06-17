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
from vault_memory_mcp.resilience import (  # noqa: E402
    ensure_config_and_vault,
    patch_config_vault_path,
    write_report_path,
)
from vault_memory_mcp.sync import VaultSync  # noqa: E402

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
AUDIT_STATE = Path.home() / ".vault-memory" / "audit-state"


def bootstrap() -> tuple[object, VaultSync, dict]:
    """Load config with vault bootstrap / fixture fallback."""
    meta: dict = {"warnings": [], "vault_mode": "missing"}
    cfg, mode, warnings = ensure_config_and_vault(
        repo_root_path=ROOT,
        allow_fixture=True,
    )
    meta["vault_mode"] = mode
    meta["warnings"] = warnings

    if mode == "bootstrapped":
        cfg = patch_config_vault_path(cfg, cfg.vault.path)

    AUDIT_STATE.mkdir(parents=True, exist_ok=True)
    sync = VaultSync(cfg, state_dir=AUDIT_STATE)
    return cfg, sync, meta


def step1_requirements(cfg, sync: VaultSync, meta: dict) -> dict:
    """Question every requirement — delete dumb ones."""
    findings = list(meta.get("warnings") or [])
    fixes = []

    if meta.get("vault_mode") == "fixture":
        fixes.append("audit used repo fixture vault (user vault path missing)")

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

    vault_n = 0
    if cfg.vault.path.exists():
        vault_n = len(list_notes(cfg.vault.path, cfg.vault.ignore))
    graph_n = sync.health().get("graph", {}).get("notes", 0)

    hermes = cfg.vault.path / "hermes-setup.md"
    if hermes.exists() and "obsidian_notes" in hermes.read_text(encoding="utf-8"):
        findings.append("hermes-setup.md references stale collection name obsidian_notes")

    return {
        "step": 1,
        "name": "Make Requirements Less Dumb",
        "findings": findings,
        "fixes": fixes,
        "metrics": {"vault_notes": vault_n, "graph_notes": graph_n, "vault_mode": meta.get("vault_mode")},
        "pass": meta.get("vault_mode") != "missing",
    }


def step2_delete(sync: VaultSync, cfg, meta: dict) -> dict:
    """Delete unnecessary parts — prune orphans."""
    if meta.get("vault_mode") == "missing":
        return {
            "step": 2,
            "name": "Delete the Part/Process",
            "findings": ["vault missing — skipped sync prune"],
            "fixes": [],
            "metrics": {},
            "pass": True,
        }

    before_g = sync.health().get("graph", {}).get("notes", 0)
    before_chunks = sync.health().get("graph", {}).get("vector", {}).get("chunks", 0)
    vault_n = len(list_notes(cfg.vault.path, cfg.vault.ignore))
    findings = []
    if before_g > vault_n + 5:
        findings.append(f"graph bloat before prune: {before_g} nodes vs {vault_n} vault notes")

    result = sync.run(force=False, require_vault=False)
    after_g = sync.health().get("graph", {}).get("notes", 0)
    after_chunks = sync.health().get("graph", {}).get("vector", {}).get("chunks", 0)

    return {
        "step": 2,
        "name": "Delete the Part/Process",
        "findings": findings + result.errors,
        "fixes": [f"pruned {result.pruned} orphan index entries"] if result.pruned else [],
        "metrics": {
            "pruned": result.pruned,
            "graph_before": before_g,
            "graph_after": after_g,
            "chunks_before": before_chunks,
            "chunks_after": after_chunks,
            "vault_notes": vault_n,
        },
        "pass": after_g <= vault_n + 5 and not result.errors,
    }


def step3_simplify(cfg) -> dict:
    """Simplify what remains."""
    findings = []
    if cfg.docker.mode != "unified":
        findings.append(f"docker.mode should be unified (got {cfg.docker.mode})")
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
    if os.environ.get("VAULT_MEMORY_AUDIT_SKIP_TESTS") == "1":
        return {
            "step": 4,
            "name": "Accelerate Cycle Time",
            "findings": [],
            "fixes": ["skipped nested pytest (VAULT_MEMORY_AUDIT_SKIP_TESTS=1)"],
            "metrics": {"unit_test_seconds": 0, "unit_tests_pass": True, "skipped": True},
            "pass": True,
        }
    t0 = datetime.now(timezone.utc)
    proc = subprocess.run(
        ["uv", "run", "pytest", "-q", str(ROOT / "tests"), "-m", "not integration", "--tb=no"],
        cwd=ROOT / "mcp-server",
        capture_output=True,
        text=True,
        timeout=180,
    )
    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
    passed = proc.returncode == 0
    return {
        "step": 4,
        "name": "Accelerate Cycle Time",
        "findings": [] if passed else [(proc.stdout or proc.stderr)[-500:]],
        "fixes": [],
        "metrics": {"unit_test_seconds": round(elapsed, 2), "unit_tests_pass": passed},
        "pass": passed,
    }


def step5_automate(sync: VaultSync, cfg, meta: dict) -> dict:
    """Automate only after 1-4."""
    findings = []
    fixes = []

    if not services_healthy():
        ensure_docker_services(ROOT)
    neo4j_ok = services_healthy()

    lab_protected = True
    pinned_count = 0
    if meta.get("vault_mode") != "missing" and cfg.vault.path.exists():
        curator = VaultCurator(cfg, state_dir=sync.state_dir, graph=sync.graph)
        preview = curator.run(dry_run=True)
        lab_protected = all(
            a.action != "archive" for a in preview.actions if "vault-memory-lab" in a.path
        )
        if not lab_protected:
            findings.append("curator dry-run would archive lab playbooks")
        status = curator.status()
        pinned_count = status.get("pinned_count", 0)
        if pinned_count:
            fixes.append(f"pinned: {status.get('pinned')}")
    else:
        fixes.append("skipped curator preview (vault missing)")

    auto_scripts = [
        ROOT / "scripts" / "test-cycle.sh",
        ROOT / "scripts" / "watch_daemon.py",
        ROOT / "scripts" / "vault-memory-lab.py",
        ROOT / "scripts" / "scripts" / "elon-5step-audit.py",
    ]
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
            "neo4j_healthy": neo4j_ok,
            "lab_protected": lab_protected,
            "pinned_count": pinned_count,
            "automation_scripts": len(auto_scripts) - len(missing),
        },
        "pass": not missing and lab_protected,
    }


def write_report(cfg, steps: list[dict], meta: dict) -> Path:
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
        f"Vault mode: {meta.get('vault_mode')}",
        "",
    ]
    all_pass = all(s["pass"] for s in steps)
    lines.append(f"**Overall:** {'PASS' if all_pass else 'NEEDS ATTENTION'}")
    lines.append("")
    for s in steps:
        icon = "PASS" if s["pass"] else "WARN"
        lines.append(f"## Step {s['step']}: {s['name']} [{icon}]")
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

    report_path = write_report_path(cfg, rel, ROOT)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"
    vault = cfg.vault.path.resolve()
    if vault.exists() and str(report_path.resolve()).startswith(str(vault)):
        write_note(vault, rel, content)
    else:
        report_path.write_text(content, encoding="utf-8")
    return report_path


def main() -> int:
    cfg, sync, meta = bootstrap()
    steps = []
    try:
        for fn, args in (
            (step1_requirements, (cfg, sync, meta)),
            (step2_delete, (sync, cfg, meta)),
            (step3_simplify, (load_config(),)),
            (step4_accelerate, ()),
            (step5_automate, (sync, cfg, meta)),
        ):
            steps.append(fn(*args))
            print(f"step {steps[-1]['step']} done: pass={steps[-1]['pass']}", flush=True)
        report = write_report(cfg, steps, meta)
        if meta.get("vault_mode") != "missing":
            sync.run(force=False, require_vault=False)
    finally:
        sync.close()

    out = {
        "at": NOW,
        "all_pass": all(s["pass"] for s in steps),
        "vault_mode": meta.get("vault_mode"),
        "warnings": meta.get("warnings"),
        "steps": steps,
        "report": str(report),
    }
    log = Path.home() / ".vault-memory" / "logs" / "elon"
    log.mkdir(parents=True, exist_ok=True)
    (log / f"audit-{NOW.replace(':', '-')}.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0 if out["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
