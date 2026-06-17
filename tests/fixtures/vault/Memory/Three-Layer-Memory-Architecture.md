---
source: internal://vault-memory
source_type: policy
owner: vault-memory
added: 2026-06-17
last_verified: 2026-06-17
confidence: 1.0
spoil_after_days: 3650
memory_policy: '[[Long-Term-Memory-Policy]]'
tags: [policy, agent-memory]
type: policy
---

# Three-Layer Memory Architecture

Agentic systems use two stores with distinct abstraction levels:

## Layer 1 — Concrete (graph store)

Least abstract. Machine-queryable graph nodes:

- `:TestRun` — command, cwd, exit_code, expected, actual, outcome
- `:Fact` → `:Source` — provenance chain per vault note
- `:Chunk` — vector embeddings for semantic retrieval

Use `provenance_trail` and `query_agent_guidance` for concrete recreation data.

## Layer 2 — Abstract (Obsidian MD)

More abstract. Human/agent-readable prose in `Memory/Agent/`:

| Folder | Purpose |
|--------|---------|
| `Solutions/` | Verified approaches that work (`type: solution`) |
| `Anti-Patterns/` | Failures to avoid (`type: anti-pattern`) |
| `Lessons/` | Distilled patterns (`type: lesson`) |

## Agent workflow

1. **Before task:** `query_agent_guidance` — get solutions + anti-patterns
2. **After success:** `add_agent_memory` with `memory_type: solution` + `verified_in` recreation metadata
3. **After failure:** `add_agent_memory` with `memory_type: anti-pattern` + failure details (cases A–F)
4. **Periodic:** `run_curator` — protects agent memory paths automatically
