---
source: internal://vault-memory
source_type: policy
owner: vault-memory
added: 2026-06-17
last_verified: 2026-06-17
confidence: 1.0
spoil_after_days: 3650
memory_policy: '[[Long-Term-Memory-Policy]]'
tags: [policy, memory]
type: policy
---

# Long-Term Memory Policy

Hub policy for vault-memory provenance notes under `Memory/`.

- All `Memory/` notes require provenance frontmatter (`source`, `verified_in`, etc.)
- Agent task memory lives in `Memory/Agent/` — see [[Three-Layer-Memory-Architecture]]
- Test recreation rules: [[Test-Memory-Recreation-Policy]]
