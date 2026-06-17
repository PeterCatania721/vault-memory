"""Provenance frontmatter schema + Neo4j Fact/Source/TestRun graph layer."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import hashlib

import yaml

from .graph import GraphStore
from .obsidian import merge_frontmatter, read_note, split_frontmatter, write_note

REQUIRED_FRONTMATTER = ("source", "source_type", "added", "confidence", "spoil_after_days")
MEMORY_REQUIRED = REQUIRED_FRONTMATTER + ("last_verified", "memory_policy")
OPTIONAL_FRONTMATTER = ("verified_in", "owner", "tags", "related_to", "contradicts", "used_by")

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")


def parse_frontmatter(content: str) -> dict[str, Any]:
    fm, _ = split_frontmatter(content)
    return fm


def validate_frontmatter(fm: dict[str, Any], *, memory_note: bool = False) -> list[str]:
    issues: list[str] = []
    required = MEMORY_REQUIRED if memory_note else REQUIRED_FRONTMATTER
    for key in required:
        if key not in fm or fm[key] in (None, ""):
            issues.append(f"missing {key}")
    if "verified_in" in fm and fm["verified_in"] is not None:
        if not isinstance(fm["verified_in"], list):
            issues.append("verified_in must be a list")
        else:
            for i, entry in enumerate(fm["verified_in"]):
                if not isinstance(entry, dict):
                    issues.append(f"verified_in[{i}] must be a dict")
                    continue
                for req in ("test_id", "date", "outcome"):
                    if not entry.get(req):
                        issues.append(f"verified_in[{i}] missing {req}")
    if "confidence" in fm:
        try:
            c = float(fm["confidence"])
            if not 0 <= c <= 1:
                issues.append("confidence must be 0-1")
        except (TypeError, ValueError):
            issues.append("confidence must be numeric")
    return issues


def stable_fact_id(rel_path: str) -> str:
    return hashlib.sha256(rel_path.encode()).hexdigest()[:32]


def build_research_frontmatter(
    *,
    source: str,
    source_type: str,
    confidence: float = 0.8,
    spoil_after_days: int = 180,
    verified_in: list[dict[str, Any]] | None = None,
    owner: str = "Peter Catania / AI agent",
    tags: list[str] | None = None,
    related_to: list[str] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "source": source,
        "source_type": source_type,
        "owner": owner,
        "added": now,
        "last_verified": now,
        "verified_in": verified_in or [],
        "confidence": confidence,
        "spoil_after_days": spoil_after_days,
        "tags": tags or ["research", "hermes-memory", "long-term"],
        "related_to": related_to or ["[[Long-Term-Memory-Policy]]"],
        "memory_policy": "[[Long-Term-Memory-Policy]]",
    }


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) == 10:
            dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def spoil_status(fm: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Return spoil evaluation from frontmatter."""
    now = now or datetime.now(timezone.utc)
    added = _parse_date(str(fm.get("added", "")))
    last_verified = _parse_date(str(fm.get("last_verified", "")))
    spoil_days = int(fm.get("spoil_after_days") or 0)
    anchor = last_verified or added
    spoiled = False
    reason = ""
    if anchor and spoil_days > 0:
        if anchor + timedelta(days=spoil_days) < now:
            spoiled = True
            reason = f"spoil_after_days ({spoil_days}) exceeded since {anchor.date()}"

    verified = fm.get("verified_in") or []
    recent_success = False
    for entry in verified if isinstance(verified, list) else []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("outcome", "")).lower() != "success":
            continue
        vdate = _parse_date(str(entry.get("date", "")))
        if vdate and (now - vdate).days <= 90:
            recent_success = True
            break

    unverified_stale = spoiled and not recent_success
    return {
        "spoiled": spoiled,
        "unverified_stale": unverified_stale,
        "recent_verification": recent_success,
        "reason": reason,
    }


class ProvenanceStore:
    """Write structured provenance into Neo4j alongside vault notes."""

    def __init__(self, graph: GraphStore, vault_path: Path):
        self.graph = graph
        self.vault_path = vault_path

    def upsert_from_note(self, rel_path: str) -> dict[str, Any]:
        note = read_note(self.vault_path, rel_path)
        fm = parse_frontmatter(note.content)
        is_memory = rel_path.startswith("Memory/") and not rel_path.startswith("Memory/Curator-Logs/")
        issues = validate_frontmatter(fm, memory_note=is_memory)
        if issues and is_memory:
            return {"ok": False, "path": rel_path, "issues": issues}
        if issues and not rel_path.startswith("Memory/"):
            return {"ok": False, "path": rel_path, "issues": issues}

        source = str(fm.get("source", "unknown"))
        fact_id = stable_fact_id(rel_path)
        verified = fm.get("verified_in") or []
        spoil_days = int(fm.get("spoil_after_days", 180))

        with self.graph._session() as session:
            session.run(
                """
                MERGE (n:Note {path: $path})
                SET n.title = $title, n.layer = 'memory', n.updated_at = timestamp()
                MERGE (s:Source {url: $source})
                SET s.source_type = $source_type,
                    s.owner = $owner,
                    s.added = $added,
                    s.last_verified = $last_verified
                MERGE (f:Fact {id: $fact_id})
                SET f.path = $path,
                    f.confidence = $confidence,
                    f.spoil_after_days = $spoil_days,
                    f.summary = $title,
                    f.last_verified = $last_verified
                MERGE (n)-[:DOCUMENTS]->(f)
                MERGE (f)-[:SOURCED_FROM]->(s)
                MERGE (f)-[r:SPOIL_AFTER]->(p:SpoilPolicy {days: $spoil_days})
                SET r.days = $spoil_days
                """,
                path=rel_path,
                title=note.title,
                source=source,
                source_type=str(fm.get("source_type", "unknown")),
                owner=str(fm.get("owner", "")),
                added=str(fm.get("added", "")),
                last_verified=str(fm.get("last_verified", "")),
                fact_id=fact_id,
                confidence=float(fm.get("confidence", 0.5)),
                spoil_days=spoil_days,
            )

            for entry in verified if isinstance(verified, list) else []:
                if not isinstance(entry, dict):
                    continue
                tid = str(entry.get("test_id") or "")
                if not tid:
                    continue
                version = str(entry.get("software_version") or entry.get("version") or "")
                system = str(entry.get("system") or "")
                session.run(
                    """
                    MATCH (f:Fact {id: $fact_id})
                    MERGE (t:TestRun {id: $tid})
                    SET t.date = $date,
                        t.outcome = $outcome,
                        t.software_version = $version,
                        t.system = $system
                    MERGE (f)-[:VERIFIED_IN]->(t)
                    WITH t, $version AS ver, $system AS sys
                    FOREACH (_ IN CASE WHEN ver <> '' THEN [1] ELSE [] END |
                        MERGE (v:Version {name: ver})
                        MERGE (t)-[:RAN_VERSION]->(v))
                    FOREACH (_ IN CASE WHEN sys <> '' THEN [1] ELSE [] END |
                        MERGE (s:System {name: sys})
                        MERGE (t)-[:RAN_ON]->(s))
                    """,
                    fact_id=fact_id,
                    tid=tid,
                    date=str(entry.get("date", "")),
                    outcome=str(entry.get("outcome", "")),
                    version=version,
                    system=system,
                )

            for raw in fm.get("related_to") or []:
                target = str(raw).strip("[]")
                if not target:
                    continue
                session.run(
                    """
                    MATCH (f:Fact {id: $fact_id})
                    MERGE (dst:Note {title: $target})
                    ON CREATE SET dst.path = $target
                    MERGE (f)-[:RELATED_TO]->(dst)
                    """,
                    fact_id=fact_id,
                    target=target,
                )

            for raw in fm.get("contradicts") or []:
                target = str(raw).strip("[]")
                if not target:
                    continue
                session.run(
                    """
                    MATCH (f:Fact {id: $fact_id})
                    MERGE (other:Note {title: $target})
                    ON CREATE SET other.path = $target
                    MERGE (f)-[:CONTRADICTS]->(other)
                    """,
                    fact_id=fact_id,
                    target=target,
                )

            for raw in fm.get("used_by") or []:
                target = str(raw).strip("[]")
                if not target:
                    continue
                session.run(
                    """
                    MATCH (f:Fact {id: $fact_id})
                    MERGE (user:Note {title: $target})
                    ON CREATE SET user.path = $target
                    MERGE (user)-[:USED_BY]->(f)
                    """,
                    fact_id=fact_id,
                    target=target,
                )

        return {
            "ok": True,
            "path": rel_path,
            "fact_id": fact_id,
            "source": source,
            "issues": issues,
            "verification_count": len(verified) if isinstance(verified, list) else 0,
        }

    def query_unverified_stale(self, days: int = 90, source_type: str | None = None) -> list[dict[str, Any]]:
        """Facts with no successful verification in last N days (optional source_type filter)."""
        with self.graph._session() as session:
            rows = session.run(
                """
                MATCH (f:Fact)-[:SOURCED_FROM]->(s:Source)
                WHERE ($source_type IS NULL OR s.source_type = $source_type)
                OPTIONAL MATCH (f)-[:VERIFIED_IN]->(t:TestRun)
                WITH f, s,
                     [x IN collect(t) WHERE x.outcome = 'success'
                      AND x.date >= date() - duration({days: $days})] AS recent_success
                WHERE size(recent_success) = 0
                RETURN f.path AS path, f.confidence AS confidence,
                       s.url AS source, s.source_type AS source_type,
                       s.last_verified AS last_verified, f.spoil_after_days AS spoil_after_days
                ORDER BY f.confidence ASC
                LIMIT 50
                """,
                days=days,
                source_type=source_type,
            )
            return [dict(r) for r in rows]

    def provenance_trail(self, rel_path: str, depth: int = 2) -> dict[str, Any]:
        with self.graph._session() as session:
            fact = session.run(
                """
                MATCH (n:Note {path: $path})-[:DOCUMENTS]->(f:Fact)
                OPTIONAL MATCH (f)-[:SOURCED_FROM]->(s:Source)
                OPTIONAL MATCH (f)-[:VERIFIED_IN]->(t:TestRun)
                OPTIONAL MATCH (t)-[:RAN_VERSION]->(v:Version)
                OPTIONAL MATCH (t)-[:RAN_ON]->(sys:System)
                OPTIONAL MATCH (f)-[:SPOIL_AFTER]->(p:SpoilPolicy)
                RETURN f.id AS fact_id, s.url AS source, f.spoil_after_days AS spoil_after_days,
                       collect(DISTINCT t) AS tests,
                       collect(DISTINCT v.name) AS versions,
                       collect(DISTINCT sys.name) AS systems
                """,
                path=rel_path,
            ).single()
            neighbors = self.graph.neighbors(rel_path, depth=depth)
        if not fact:
            return {"path": rel_path, "found": False, "neighbors": neighbors}
        return {
            "path": rel_path,
            "found": True,
            "fact_id": fact["fact_id"],
            "source": fact["source"],
            "spoil_after_days": fact.get("spoil_after_days"),
            "tests": [dict(t) for t in (fact["tests"] or []) if t],
            "versions": [v for v in (fact.get("versions") or []) if v],
            "systems": [s for s in (fact.get("systems") or []) if s],
            "neighbors": neighbors,
        }


def hybrid_search(
    graph: GraphStore,
    query: str,
    limit: int = 5,
    depth: int = 2,
    vault_path: Path | None = None,
) -> list[dict[str, Any]]:
    """GraphRAG default: semantic hits + graph neighbors + provenance trail."""
    hits = graph.search_with_graph_context(query, limit=limit, depth=depth)
    store = ProvenanceStore(graph, vault_path or Path(".")) if vault_path else None
    out: list[dict[str, Any]] = []
    for hit in hits:
        path = hit.get("path") or ""
        trail: dict[str, Any] = {}
        if path and store:
            try:
                trail = store.provenance_trail(path, depth=1)
            except Exception:
                trail = {}
        out.append({**hit, "provenance": trail})
    return out


def write_research_note(
    vault_path: Path,
    rel_path: str,
    title: str,
    body: str,
    frontmatter: dict[str, Any],
) -> str:
    header = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    content = f"---\n{header}\n---\n\n# {title}\n\n{body.strip()}\n"
    write_note(vault_path, rel_path, content)
    return rel_path