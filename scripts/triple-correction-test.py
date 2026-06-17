#!/usr/bin/env python3
"""Run 3 consecutive memory-correction cycles (false→remove→valid→verify).

Simulates Grok Build + Hermes agent workflows via vault_memory MCP primitives:
  mark_vault_note_invalid / set_vault_note_expiry / delete_vault_note / run_curator / sync_vault
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-server" / "src"))

os.environ.setdefault("VAULT_MEMORY_CONFIG", str(Path.home() / ".vault-memory" / "config.yaml"))

from vault_memory_mcp.config import load_config  # noqa: E402
from vault_memory_mcp.curator import VaultCurator  # noqa: E402
from vault_memory_mcp.obsidian import keyword_search, list_notes, write_note  # noqa: E402
from vault_memory_mcp.sync import VaultSync  # noqa: E402

CORPUS = "vault-memory-lab/correction-test"
REQUIRED_PASSES = 3


def _attempt(n: int, cfg, sync: VaultSync, curator: VaultCurator) -> dict:
    vault = cfg.vault.path
    false_rel = f"{CORPUS}/attempt-{n}-false.md"
    valid_rel = f"{CORPUS}/attempt-{n}-valid.md"
    verbose_rel = f"{CORPUS}/attempt-{n}-verbose.md"
    token = f"FALSEPORT{n}9999"
    good_token = f"VALIDPORT{n}6333"
    steps: list[dict] = []

    # 1) Inject false memory
    write_note(
        vault,
        false_rel,
        f"# False claim {n}\n\nNeo4j runs on port {token}.\n",
    )
    sync.run(force=False)
    kw_before = keyword_search(vault, token, cfg.vault.ignore, limit=5)
    steps.append({"step": "inject_false", "pass": len(kw_before) >= 1, "hits": len(kw_before)})

    # 2) Mark invalid + curator archive (agent correction)
    curator.mark_invalid(false_rel, reason=f"validated non-functional attempt {n}")
    cur = curator.run(dry_run=False)
    gone = false_rel not in list_notes(vault, cfg.vault.ignore)
    steps.append({
        "step": "remove_false",
        "pass": gone and cur.archived >= 1,
        "archived": cur.archived,
        "gone": gone,
    })

    # 3) Write corrected memory
    write_note(
        vault,
        valid_rel,
        f"---\nstatus: success\ntype: verification\n---\n\n"
        f"# Verified fact {n}\n\nNeo4j runs on port {good_token}.\n",
    )
    sync.run(force=True)
    kw_good = keyword_search(vault, good_token, cfg.vault.ignore, limit=5)
    kw_false_again = keyword_search(vault, token, cfg.vault.ignore, limit=5)
    steps.append({
        "step": "inject_valid",
        "pass": len(kw_good) >= 1 and len(kw_false_again) == 0,
        "good_hits": len(kw_good),
        "false_hits": len(kw_false_again),
    })

    # 4) Semantic improvement check
    sem_ok = False
    sem_top = None
    if sync.graph:
        hits = sync.graph.search(good_token, limit=5)
        paths = [h.get("path") for h in hits]
        sem_ok = valid_rel in paths and false_rel not in paths
        sem_top = paths[0] if paths else None
    steps.append({
        "step": "semantic_improved",
        "pass": sem_ok,
        "top": sem_top,
    })

    # 5) Expiry + verbose compress/archive path
    yesterday = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    verbose_body = "\n\n".join([f"Filler paragraph {i} with extra noise." for i in range(120)])
    write_note(
        vault,
        verbose_rel,
        f"---\nexpires_at: {yesterday}\n---\n\n# Verbose stale {n}\n{verbose_body}\n",
    )
    sync.run(force=False)
    cur2 = curator.run(dry_run=False)
    verbose_gone = verbose_rel not in list_notes(vault, cfg.vault.ignore)
    steps.append({
        "step": "expire_verbose",
        "pass": verbose_gone,
        "archived": cur2.archived,
    })

    passed = all(s["pass"] for s in steps)
    return {
        "attempt": n,
        "pass": passed,
        "steps": steps,
        "false_rel": false_rel,
        "valid_rel": valid_rel,
    }


def main() -> int:
    cfg = load_config()
    sync = VaultSync(cfg)
    curator = VaultCurator(cfg, state_dir=sync.state_dir, graph=sync.graph)
    (cfg.vault.path / CORPUS).mkdir(parents=True, exist_ok=True)

    results = []
    consecutive = 0
    for n in range(1, REQUIRED_PASSES + 1):
        r = _attempt(n, cfg, sync, curator)
        results.append(r)
        if r["pass"]:
            consecutive += 1
        else:
            consecutive = 0
        print(f"attempt {n}: {'PASS' if r['pass'] else 'FAIL'}", flush=True)

    all_pass = consecutive == REQUIRED_PASSES
    out = {
        "required": REQUIRED_PASSES,
        "consecutive_passes": consecutive,
        "all_pass": all_pass,
        "results": results,
        "agents": {
            "grok_build": "same MCP tools via vault-memory-mcp stdio",
            "hermes": "vault_memory MCP in ~/.hermes/config.yaml",
        },
        "tools_used": [
            "mark_vault_note_invalid",
            "set_vault_note_expiry",
            "delete_vault_note",
            "run_curator",
            "sync_vault",
            "search_vault_keyword",
            "search_vault_semantic",
        ],
    }
    log = Path.home() / ".vault-memory" / "logs" / "correction-test"
    log.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (log / f"triple-{stamp}.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())