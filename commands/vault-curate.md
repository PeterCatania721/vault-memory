---
description: Run vault-memory curator cycle (archive stale, compress verbose, protect success data)
---

Run the vault-memory curator:

1. Call `curator_status` to see thresholds and last run.
2. Call `run_curator` with `dry_run=true` and `force=true` to preview actions.
3. If the preview looks correct, call `run_curator` with `force=true` for a live pass.
4. Summarize archived/compressed/protected counts from the result.

Never archive notes tagged `#test-success`, `#playbook`, or with `status: success` frontmatter.