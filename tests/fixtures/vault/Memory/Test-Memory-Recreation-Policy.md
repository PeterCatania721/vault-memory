---
source: internal://vault-memory
source_type: policy
owner: vault-memory
added: 2026-06-17
last_verified: 2026-06-17
confidence: 1.0
spoil_after_days: 3650
memory_policy: '[[Long-Term-Memory-Policy]]'
tags: [policy, test-memory]
type: policy
---

# Test Memory Recreation Policy

Every agent memory write (`add_agent_memory`) for **solution** or **anti-pattern** must include `verified_in` with:

| Field | Required | Purpose |
|-------|----------|---------|
| `test_id` | yes | Stable case id (e.g. case-a, case-b) |
| `date` | yes | ISO date |
| `outcome` | yes | `success` or `failure` |
| `command` | yes | Exact command to reproduce |
| `cwd` | yes | Working directory |
| `exit_code` | yes | Process exit code |
| `expected` | anti-pattern | What should have happened |
| `actual` | anti-pattern | What happened instead |
| `git_commit` | recommended | Repo state |
| `system` | recommended | Host/environment |

Solutions require `outcome: success`. Anti-patterns require `outcome: failure`.
