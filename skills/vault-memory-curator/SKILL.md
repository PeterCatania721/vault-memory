---
name: vault-memory-curator
description: >
  Run the vault-memory curator (Hermes-style cyclic maintenance with Elon 5-step
  algorithm). Archives stale notes, compresses verbose unused notes, protects
  success/playbook/replicable test memory. Use when vault is bloated, after long
  idle periods, or runs /vault-curate.
---

# vault-memory Curator

Hermes curator analogue for Obsidian vault memory. Runs in **cycles** (default every 7 days).

## Elon 5-step cycle (each pass)

| Step | Action |
|------|--------|
| 1 | Question requirements — score notes; protect pins/success/playbooks |
| 2 | Delete — archive stale unused notes (recoverable) |
| 3 | Simplify — compress verbose long-unused notes in-place |
| 4 | Accelerate — incremental scan, batched actions |
| 5 | Automate — watch daemon + session hook + MCP |

## MCP tools

| Tool | Purpose |
|------|---------|
| `curator_status` | Last run, thresholds, pinned notes |
| `run_curator` | Execute cycle (`dry_run=true` to preview) |
| `curator_pin` / `curator_unpin` | Protect a note from archive/compress |
| `curator_restore` | Restore from `~/.vault-memory/archive/` |

## Protect notes from curation

Any of:

- Frontmatter: `curator: pin`, `vault-memory: protected`, `status: success`, `type: playbook`
- Tags: `#pinned`, `#test-success`, `#playbook`, `#replicable`
- Path globs in config `curator.protect_paths`
- `curator_pin` MCP tool

## Configure

```bash
get_config   # read curator.* section
update_config  # e.g. {"curator": {"archive_after_days": 120}}
```

## Manual run

```bash
# Preview (no mutations)
run_curator(dry_run=true, force=true)

# Force live run (bypass interval gate)
run_curator(force=true)
```

## CLI daemon

```bash
python scripts/watch_daemon.py   # sync + curator on interval
```

## Recovery

Archived notes live under `~/.vault-memory/archive/YYYY-MM-DD/`. Use `curator_restore` or move files back into the vault.