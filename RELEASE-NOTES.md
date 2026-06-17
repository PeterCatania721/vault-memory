# Release notes

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