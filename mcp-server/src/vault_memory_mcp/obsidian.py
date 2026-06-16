"""Obsidian vault filesystem access — proven mcp-obsidian pattern."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]]*)?(?:\|[^\]]*)?\]\]")


@dataclass
class Note:
    path: str
    title: str
    content: str
    mtime: float
    content_hash: str
    wikilinks: list[str]


def _matches_ignore(rel: str, patterns: list[str]) -> bool:
    from fnmatch import fnmatch

    for pattern in patterns:
        if fnmatch(rel, pattern) or fnmatch(rel, pattern.lstrip("./")):
            return True
    return False


def list_notes(vault_path: Path, ignore: list[str] | None = None) -> list[str]:
    ignore = ignore or []
    notes: list[str] = []
    for path in sorted(vault_path.rglob("*.md")):
        rel = str(path.relative_to(vault_path))
        if _matches_ignore(rel, ignore):
            continue
        notes.append(rel)
    return notes


def read_note(vault_path: Path, rel_path: str) -> Note:
    full = (vault_path / rel_path).resolve()
    if not str(full).startswith(str(vault_path.resolve())):
        raise ValueError(f"Path escapes vault: {rel_path}")
    if not full.exists():
        raise FileNotFoundError(rel_path)
    content = full.read_text(encoding="utf-8", errors="replace")
    stat = full.stat()
    title = full.stem
    links = [m.group(1).strip() for m in WIKILINK_RE.finditer(content)]
    digest = hashlib.sha256(content.encode()).hexdigest()[:16]
    return Note(
        path=rel_path,
        title=title,
        content=content,
        mtime=stat.st_mtime,
        content_hash=digest,
        wikilinks=links,
    )


def keyword_search(vault_path: Path, query: str, ignore: list[str] | None = None, limit: int = 20) -> list[dict]:
    query_lower = query.lower()
    results: list[dict] = []
    for rel in list_notes(vault_path, ignore):
        note = read_note(vault_path, rel)
        if query_lower in note.content.lower() or query_lower in note.title.lower():
            snippet = _snippet(note.content, query_lower)
            results.append({"path": note.path, "title": note.title, "snippet": snippet, "score": 1.0})
        if len(results) >= limit:
            break
    return results


def _snippet(content: str, query: str, radius: int = 120) -> str:
    idx = content.lower().find(query)
    if idx < 0:
        return content[: radius * 2].strip()
    start = max(0, idx - radius)
    end = min(len(content), idx + len(query) + radius)
    return content[start:end].strip()


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Header-aware chunking — split on ## headers first, then size."""
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("#") and current:
            sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))

    chunks: list[str] = []
    for section in sections:
        if len(section) <= chunk_size:
            chunks.append(section.strip())
            continue
        start = 0
        while start < len(section):
            end = start + chunk_size
            chunks.append(section[start:end].strip())
            start = end - overlap
    return [c for c in chunks if c]