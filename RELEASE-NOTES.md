# Release notes

## 0.2.4 — 2026-06-17 (Elon algorithm pass)

**01 Less dumb requirements:** `add_agent_memory` enforces recreation metadata (`command`, `cwd`, `exit_code`) for solutions and anti-patterns.

**02 Delete:** Removed `search_vault_graphrag` (use `search_vault_hybrid`), dead `:Verification` index, Qdrant migration to `scripts/archive/`, `docker-compose.separate.yml`, deprecated `vector.url`/`collection`.

**03 Optimize:** CPU-only PyTorch pin; semantic ranking for failure `TestRun` nodes; renamed MCP tool `query_agent_guidance` (dropped `_tool` suffix).

**04 Accelerate:** `docker-up.sh` auto-starts dockerd on restricted cloud VMs (`vfs` + no iptables).

**05 Automate:** Curator skips vault log writes on dry-run; protects only `Solutions/` + `Anti-Patterns/` (lessons can age out).

- Policy stubs shipped in test fixtures: `Long-Term-Memory-Policy`, `Test-Memory-Recreation-Policy`
- **25 MCP tools** (was 26)

## 0.2.3 — 2026-06-17

- **Agentic memory layer** — two-tier architecture: concrete Neo4j (`TestRun` with command/cwd/exit_code) + abstract Obsidian (`Memory/Agent/Solutions|Anti-Patterns|Lessons`)
- MCP: `add_agent_memory`, `query_agent_guidance` (success-boosted ranking, failure anti-patterns)
- TestRun nodes store full recreation metadata from `verified_in`
- Curator protects `Memory/Agent/**` and anti-pattern notes
- Cloud-tested with Docker Neo4j (81 tests pass)

## 0.2.2 — 2026-06-17

- Fix `provenance_trail` returning `found: false` when note YAML has `verified_in` but Neo4j Fact chain was never materialized
- `sync_vault` now upserts Fact/Source/TestRun graph for Memory/ notes (and other provenance-frontmatter notes) on each indexed change
- `provenance_trail` lazy-upserts from vault frontmatter when the graph chain is missing

## 0.2.1 — 2026-06-17

- Provenance GraphRAG: `search_vault_hybrid`, `provenance_trail`, `query_stale_facts`
- Stable Fact IDs; Version/System nodes; SPOIL_AFTER edges
- Curator log frontmatter; `add_research_memory` triggers curator preview
- Docs updated for Neo4j-only stack

## 0.2.0 — 2026-06-16

- **Neo4j-only architecture** — Qdrant removed from docker-compose and sync path
- Vectors on `:Chunk` and `:Verification` nodes (Neo4j vector indexes)
- Provenance layer: Fact/Source/TestRun graph from YAML frontmatter
- MCP: `add_research_memory`, `upsert_note_provenance`, `search_vault_hybrid`, `search_vault_graphrag`
- Rule-based curator: `spoil_after_days` + no `verified_in` success in 90d → archive
- Scripts: `add_research_memory.py`, `backfill_memory_frontmatter.py`, `migrate-qdrant-to-neo4j.py`
- 70 tests (unit + integration including provenance chain)

### Migration from 0.1.x (Qdrant + Neo4j)

| v0.1.x | v0.2+ |
|--------|-------|
| 2 Docker containers (Qdrant + Neo4j) | 1 container (Neo4j) |
| Dual sync + dual orphan prune | Single Neo4j sync |
| Semantic in Qdrant, graph in Neo4j | Both in Neo4j |
| No provenance graph | Fact → Source → TestRun in Neo4j |

Re-index from Obsidian: `sync_vault force=true`. Optional one-shot: `scripts/migrate-qdrant-to-neo4j.py`.

## 0.1.2 — 2026-06-16

- Curator: Elon-style archive/compress with pin/protect rules
- Memory correction tools: `mark_vault_note_invalid`, `set_vault_note_expiry`, `delete_vault_note`
- Sync orphan pruning for Qdrant + Neo4j alignment
- Docker health probe (port-conflict safe)
- 63 tests (unit, environment, integration)
- Triple correction test script (3/3 consecutive pass)

## 0.1.1 — 2026-06-16

- Published to GitHub as public repository
- Status documented in `STATUS.md`
- Verified: unit + integration tests, Grok plugin validate, Grok Build install

## 0.1.0 — 2026-06-16

- Initial release: Obsidian + Qdrant + Neo4j cross-agent plugin
- MCP stdio server with AI-configurable YAML
- Docker Compose (unified / separate profiles)
- Skills, hooks, Elon test-cycle script