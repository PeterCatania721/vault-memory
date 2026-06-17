"""Tests for provenance frontmatter + spoil rules."""

from __future__ import annotations

from datetime import datetime, timezone

from vault_memory_mcp.provenance import (
    build_research_frontmatter,
    spoil_status,
    validate_frontmatter,
)


def test_validate_frontmatter_ok():
    fm = build_research_frontmatter(
        source="https://example.com",
        source_type="web",
        confidence=0.9,
        verified_in=[
            {
                "test_id": "t1",
                "date": "2026-06-17",
                "outcome": "success",
                "software_version": "v1",
                "system": "pytest",
            }
        ],
    )
    assert not validate_frontmatter(fm)
    assert not validate_frontmatter(fm, memory_note=True)


def test_stable_fact_id_deterministic():
    from vault_memory_mcp.provenance import stable_fact_id

    assert stable_fact_id("Memory/foo.md") == stable_fact_id("Memory/foo.md")
    assert stable_fact_id("Memory/foo.md") != stable_fact_id("Memory/bar.md")


def test_validate_frontmatter_missing_source():
    fm = build_research_frontmatter(source="x", source_type="web")
    del fm["source"]
    assert "missing source" in validate_frontmatter(fm)


def test_spoil_unverified_stale():
    fm = {
        "added": "2020-01-01",
        "last_verified": "2020-01-01",
        "spoil_after_days": 30,
        "verified_in": [],
    }
    now = datetime(2026, 6, 16, tzinfo=timezone.utc)
    status = spoil_status(fm, now)
    assert status["spoiled"] is True
    assert status["unverified_stale"] is True


def test_spoil_recent_verification_blocks_archive():
    fm = {
        "added": "2020-01-01",
        "last_verified": "2026-06-01",
        "spoil_after_days": 30,
        "verified_in": [{"date": "2026-06-10", "outcome": "success", "test_id": "t1"}],
    }
    now = datetime(2026, 6, 16, tzinfo=timezone.utc)
    status = spoil_status(fm, now)
    assert status["recent_verification"] is True
    assert status["unverified_stale"] is False