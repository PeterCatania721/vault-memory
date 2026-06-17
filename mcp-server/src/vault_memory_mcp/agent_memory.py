"""Agentic memory — two-tier architecture for task execution guidance.

Concrete layer (Neo4j): TestRun nodes with recreation metadata (command, cwd,
exit_code), Fact/Source graph, chunk embeddings for precise retrieval.

Abstract layer (Obsidian MD): Solutions, anti-patterns, and lessons in
Memory/Agent/ — human-readable prose agents cite for planning.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .graph import GraphStore
from .obsidian import read_note, write_note
from .provenance import (
    ProvenanceStore,
    build_research_frontmatter,
    hybrid_search,
    parse_frontmatter,
    stable_fact_id,
    validate_frontmatter,
    write_research_note,
)

MEMORY_TYPES = ("solution", "anti-pattern", "lesson")
TYPE_TO_FOLDER = {
    "solution": "Solutions",
    "anti-pattern": "Anti-Patterns",
    "lesson": "Lessons",
}
TYPE_TO_STATUS = {
    "solution": "success",
    "anti-pattern": "avoid",
    "lesson": "active",
}
ABSTRACTION_LAYER = {
    "solution": "abstract",
    "anti-pattern": "abstract",
    "lesson": "abstract",
}

VERIFIED_IN_OPTIONAL = (
    "command",
    "cwd",
    "exit_code",
    "expected",
    "actual",
    "git_commit",
    "containers",
    "software_version",
    "system",
)


def validate_verified_in_entry(entry: dict[str, Any], index: int = 0) -> list[str]:
    """Validate a single verified_in entry including recreation metadata."""
    issues: list[str] = []
    if not isinstance(entry, dict):
        return [f"verified_in[{index}] must be a dict"]
    for req in ("test_id", "date", "outcome"):
        if not entry.get(req):
            issues.append(f"verified_in[{index}] missing {req}")
    outcome = str(entry.get("outcome", "")).lower()
    if outcome and outcome not in ("success", "failure", "skipped", "error"):
        issues.append(f"verified_in[{index}] outcome must be success|failure|skipped|error")
    if "exit_code" in entry and entry["exit_code"] is not None:
        try:
            int(entry["exit_code"])
        except (TypeError, ValueError):
            issues.append(f"verified_in[{index}] exit_code must be integer")
    return issues


def build_agent_frontmatter(
    *,
    memory_type: str,
    source: str,
    source_type: str = "agent-task",
    confidence: float = 0.85,
    spoil_after_days: int = 180,
    verified_in: list[dict[str, Any]] | None = None,
    contradicts: list[str] | None = None,
    related_to: list[str] | None = None,
    task_id: str = "",
) -> dict[str, Any]:
    """Build frontmatter for agentic memory notes."""
    if memory_type not in MEMORY_TYPES:
        raise ValueError(f"memory_type must be one of {MEMORY_TYPES}")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tags = ["agent-memory", memory_type]
    if memory_type == "solution":
        tags.extend(["test-success", "replicable"])
    elif memory_type == "anti-pattern":
        tags.extend(["invalid-data", "avoid"])

    fm = build_research_frontmatter(
        source=source,
        source_type=source_type,
        confidence=confidence,
        spoil_after_days=spoil_after_days,
        verified_in=verified_in or [],
        tags=tags,
        related_to=related_to or ["[[Long-Term-Memory-Policy]]", "[[Test-Memory-Recreation-Policy]]"],
    )
    fm["type"] = memory_type
    fm["status"] = TYPE_TO_STATUS[memory_type]
    fm["abstraction_layer"] = ABSTRACTION_LAYER[memory_type]
    if task_id:
        fm["task_id"] = task_id
    if contradicts:
        fm["contradicts"] = contradicts
    return fm


def agent_memory_path(memory_type: str, slug: str, day: str | None = None) -> str:
    """Relative vault path for an agent memory note."""
    folder = TYPE_TO_FOLDER[memory_type]
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"Memory/Agent/{folder}/{slug}-{day}.md"


def write_agent_memory(
    vault_path: Path,
    *,
    memory_type: str,
    title: str,
    body: str,
    source: str,
    source_type: str = "agent-task",
    confidence: float = 0.85,
    spoil_after_days: int = 180,
    verified_in: list[dict[str, Any]] | None = None,
    contradicts: list[str] | None = None,
    related_to: list[str] | None = None,
    task_id: str = "",
) -> tuple[str, dict[str, Any], list[str]]:
    """Write agent memory note. Returns (rel_path, frontmatter, validation_issues)."""
    slug = title.lower().replace(" ", "-")[:50]
    slug = re.sub(r"[^a-z0-9-]", "", slug) or "memory"
    rel = agent_memory_path(memory_type, slug)
    fm = build_agent_frontmatter(
        memory_type=memory_type,
        source=source,
        source_type=source_type,
        confidence=confidence,
        spoil_after_days=spoil_after_days,
        verified_in=verified_in,
        contradicts=contradicts,
        related_to=related_to,
        task_id=task_id,
    )
    issues = validate_frontmatter(fm, memory_note=True)
    for i, entry in enumerate(verified_in or []):
        issues.extend(validate_verified_in_entry(entry, i))
    write_research_note(vault_path, rel, title, body, fm)
    return rel, fm, issues


def _latest_outcome(fm: dict[str, Any]) -> str:
    verified = fm.get("verified_in") or []
    if not isinstance(verified, list) or not verified:
        return ""
    latest = verified[-1]
    if isinstance(latest, dict):
        return str(latest.get("outcome", "")).lower()
    return ""


def rank_agent_hit(hit: dict[str, Any], fm: dict[str, Any] | None) -> float:
    """Re-rank semantic score for agentic task execution."""
    base = float(hit.get("score") or 0.0)
    if not fm:
        return base

    memory_type = str(fm.get("type", "")).lower()
    status = str(fm.get("status", "")).lower()
    outcome = _latest_outcome(fm)
    confidence = float(fm.get("confidence") or 0.5)

    if memory_type == "solution" or status == "success":
        base += 0.15
    if memory_type == "anti-pattern":
        base += 0.08
    if outcome == "success":
        base += 0.12
    elif outcome == "failure":
        base -= 0.15
    if status in ("invalid", "false", "superseded"):
        base -= 0.25
    if confidence >= 0.8:
        base += 0.05
    if fm.get("verified_in"):
        base += 0.05
    return round(base, 4)


def _classify_hit(path: str, fm: dict[str, Any]) -> str:
    memory_type = str(fm.get("type", "")).lower()
    if memory_type in MEMORY_TYPES:
        return memory_type
    if path.startswith("Memory/Agent/Anti-Patterns/"):
        return "anti-pattern"
    if path.startswith("Memory/Agent/Solutions/"):
        return "solution"
    if path.startswith("Memory/Agent/Lessons/"):
        return "lesson"
    status = str(fm.get("status", "")).lower()
    if status == "success" or str(fm.get("type", "")).lower() in ("playbook", "test-recipe"):
        return "solution"
    if status in ("invalid", "false") or _latest_outcome(fm) == "failure":
        return "anti-pattern"
    return "lesson"


def _enrich_hit(
    hit: dict[str, Any],
    vault_path: Path,
    store: ProvenanceStore | None,
) -> dict[str, Any]:
    path = hit.get("path") or ""
    fm: dict[str, Any] = {}
    if path:
        try:
            fm = parse_frontmatter(read_note(vault_path, path).content)
        except Exception:
            pass
    agent_score = rank_agent_hit(hit, fm)
    category = _classify_hit(path, fm)
    trail: dict[str, Any] = {}
    if path and store:
        try:
            trail = store.provenance_trail(path, depth=1)
        except Exception:
            pass
    return {
        **hit,
        "agent_score": agent_score,
        "memory_type": category,
        "abstraction_layer": fm.get("abstraction_layer", "abstract"),
        "status": fm.get("status"),
        "confidence": fm.get("confidence"),
        "latest_outcome": _latest_outcome(fm),
        "provenance": trail,
    }


def query_failure_patterns(
    graph: GraphStore,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Neo4j concrete layer: TestRuns with failure outcome linked to Facts."""
    try:
        rows = graph.query_readonly(
            """
            MATCH (f:Fact)-[:VERIFIED_IN]->(t:TestRun)
            WHERE toLower(t.outcome) = 'failure'
            OPTIONAL MATCH (n:Note {path: f.path})
            RETURN f.path AS path,
                   f.summary AS title,
                   f.confidence AS confidence,
                   t.id AS test_id,
                   t.date AS date,
                   t.outcome AS outcome,
                   t.command AS command,
                   t.cwd AS cwd,
                   t.exit_code AS exit_code,
                   t.expected AS expected,
                   t.actual AS actual,
                   t.software_version AS software_version,
                   t.system AS system
            ORDER BY t.date DESC
            LIMIT $limit
            """,
            {"limit": limit * 3},
        )
    except Exception:
        return []

    enriched: list[dict[str, Any]] = []
    query_lower = query.lower()
    for row in rows:
        item = dict(row)
        item["memory_type"] = "anti-pattern"
        item["abstraction_layer"] = "concrete"
        title = str(item.get("title") or "")
        path = str(item.get("path") or "")
        text = f"{title} {path} {item.get('command') or ''} {item.get('actual') or ''}".lower()
        overlap = sum(1 for word in query_lower.split() if len(word) > 2 and word in text)
        item["agent_score"] = 0.4 + min(overlap * 0.1, 0.5)
        enriched.append(item)

    enriched.sort(key=lambda x: x.get("agent_score", 0), reverse=True)
    return enriched[:limit]


def query_agent_guidance(
    graph: GraphStore,
    vault_path: Path,
    query: str,
    limit: int = 5,
    depth: int = 2,
) -> dict[str, Any]:
    """Optimized retrieval for agentic task execution.

    Returns tiered guidance: solutions to apply, anti-patterns to avoid,
    and abstract lessons — ranked by agent_score (success-boosted).
    """
    store = ProvenanceStore(graph, vault_path)
    raw_hits = hybrid_search(graph, query, limit=limit * 3, depth=depth, vault_path=vault_path)

    solutions: list[dict[str, Any]] = []
    anti_patterns: list[dict[str, Any]] = []
    lessons: list[dict[str, Any]] = []

    for hit in raw_hits:
        enriched = _enrich_hit(hit, vault_path, store)
        category = enriched.get("memory_type", "lesson")
        if category == "solution":
            solutions.append(enriched)
        elif category == "anti-pattern":
            anti_patterns.append(enriched)
        else:
            lessons.append(enriched)

    concrete_failures = query_failure_patterns(graph, query, limit=limit)
    seen_paths = {h.get("path") for h in anti_patterns}
    for failure in concrete_failures:
        if failure.get("path") not in seen_paths:
            anti_patterns.append(failure)
            seen_paths.add(failure.get("path"))

    solutions.sort(key=lambda x: x.get("agent_score", 0), reverse=True)
    anti_patterns.sort(key=lambda x: x.get("agent_score", 0), reverse=True)
    lessons.sort(key=lambda x: x.get("agent_score", 0), reverse=True)

    return {
        "query": query,
        "solutions": solutions[:limit],
        "anti_patterns": anti_patterns[:limit],
        "lessons": lessons[:limit],
        "ranking": (
            "agent_score = semantic_score + success_boost - failure_penalty; "
            "concrete failures from Neo4j TestRun nodes; abstract guidance from Obsidian Memory/Agent/"
        ),
    }
