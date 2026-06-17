"""Vault curator — Hermes-style cyclic memory maintenance.

Elon 5-step engineering cycle (strict order each pass):
  1. Question requirements — score notes; protect pinned/success/playbook data
  2. Delete — archive stale, unused, non-replicable notes (recoverable)
  3. Simplify — compress verbose long-unused notes in-place
  4. Accelerate — incremental candidate scan, batched actions
  5. Automate — daemon, hooks, and MCP tools trigger cycles

Invariants (Hermes curator parity):
  - Never hard-delete vault notes; archive is recoverable under state_dir/archive/
  - Pinned notes and success/playbook markers bypass all destructive actions
  - Dry-run produces a report without mutating vault or indexes
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import AppConfig, CuratorConfig
from .graph import GraphStore
from .obsidian import Note, list_notes, read_note, set_note_fields, split_frontmatter, write_note
from .provenance import spoil_status

CURATOR_STATE_FILE = "curator-state.json"
USAGE_STATE_FILE = "usage-state.json"

PROTECT_FRONTMATTER = re.compile(
    r"(?:^|\n)(?:curator|vault-memory)\s*:\s*(?:pin|protected)\b",
    re.IGNORECASE,
)
SUCCESS_FRONTMATTER = re.compile(
    r"(?:^|\n)status\s*:\s*success\b|(?:^|\n)type\s*:\s*(?:playbook|test-recipe|verification|solution)\b",
    re.IGNORECASE,
)
ANTI_PATTERN_FRONTMATTER = re.compile(
    r"(?:^|\n)type\s*:\s*anti-pattern\b",
    re.IGNORECASE,
)
PROTECT_TAGS = re.compile(
    r"#(?:pinned|test-success|playbook|replicable)\b",
    re.IGNORECASE,
)
SUCCESS_BODY = re.compile(
    r"\b(?:all tests pass(?:ed)?|tests? (?:passed|green)|verified working|"
    r"replication steps|replicable recipe|successful (?:test|run|implementation))\b",
    re.IGNORECASE,
)
INVALID_FRONTMATTER = re.compile(
    r"(?:^|\n)status\s*:\s*(?:invalid|false|superseded)\b|"
    r"(?:^|\n)validated\s*:\s*false\b|"
    r"(?:^|\n)functional\s*:\s*false\b",
    re.IGNORECASE,
)
INVALID_TAGS = re.compile(
    r"#(?:invalid-data|false-memory|superseded|non-functional)\b",
    re.IGNORECASE,
)
EXPIRES_AT_RE = re.compile(r"(?:^|\n)expires_at\s*:\s*['\"]?([^'\"\n]+)", re.IGNORECASE)
CODE_BLOCK = re.compile(r"```[\s\S]*?```", re.MULTILINE)
HEADER_LINE = re.compile(r"^#{1,6}\s", re.MULTILINE)
BULLET_LINE = re.compile(r"^[\s]*(?:[-*+]|\d+\.)\s", re.MULTILINE)
ACTION_LINE = re.compile(
    r"(?:^|\n)(?:```|`|\b(?:npm|pnpm|yarn|uv|pip|pytest|bash|curl|docker|git)\b)",
    re.IGNORECASE,
)


@dataclass
class CuratorAction:
    path: str
    action: str  # keep | protected | archive | compress | refresh
    reason: str
    elon_step: int


@dataclass
class CuratorResult:
    scanned: int = 0
    kept: int = 0
    protected: int = 0
    refreshed: int = 0
    archived: int = 0
    compressed: int = 0
    skipped: int = 0
    actions: list[CuratorAction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False
    started_at: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "kept": self.kept,
            "protected": self.protected,
            "refreshed": self.refreshed,
            "archived": self.archived,
            "compressed": self.compressed,
            "skipped": self.skipped,
            "dry_run": self.dry_run,
            "started_at": self.started_at,
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors,
            "actions": [
                {
                    "path": a.path,
                    "action": a.action,
                    "reason": a.reason,
                    "elon_step": a.elon_step,
                }
                for a in self.actions
            ],
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _atomic_json_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _default_curator_state() -> dict[str, Any]:
    return {
        "last_run_at": None,
        "last_run_duration_seconds": None,
        "last_run_summary": None,
        "last_report_path": None,
        "paused": False,
        "run_count": 0,
        "pinned": [],
    }


def _default_usage_state() -> dict[str, Any]:
    return {"notes": {}}


class UsageTracker:
    """Track note access from MCP search/read tools."""

    def __init__(self, state_dir: Path):
        self.path = state_dir / USAGE_STATE_FILE

    def load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    base = _default_usage_state()
                    base.update(data)
                    return base
            except (OSError, json.JSONDecodeError):
                pass
        return _default_usage_state()

    def save(self, data: dict[str, Any]) -> None:
        _atomic_json_write(self.path, data)

    def record(self, path: str, action: str = "access") -> None:
        data = self.load()
        notes = data.setdefault("notes", {})
        entry = notes.setdefault(path, {"count": 0, "last_access_at": None, "actions": {}})
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_access_at"] = _utc_now().isoformat()
        actions = entry.setdefault("actions", {})
        actions[action] = int(actions.get(action, 0)) + 1
        self.save(data)

    def last_access(self, path: str) -> datetime | None:
        entry = self.load().get("notes", {}).get(path)
        if not isinstance(entry, dict):
            return None
        return _parse_iso(entry.get("last_access_at"))


class VaultCurator:
    def __init__(
        self,
        config: AppConfig,
        state_dir: Path | None = None,
        graph: GraphStore | None = None,
        vector: GraphStore | None = None,  # deprecated alias for graph
    ):
        self.config = config
        self.curator = config.curator
        self.vault = config.vault.path
        self.state_dir = state_dir or Path.home() / ".vault-memory"
        self.state_path = self.state_dir / CURATOR_STATE_FILE
        self.archive_root = self.state_dir / "archive"
        self.reports_root = self.state_dir / "logs" / "curator"
        self.usage = UsageTracker(self.state_dir)
        self.graph = graph or vector

    def load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    base = _default_curator_state()
                    base.update({k: v for k, v in data.items() if k in base or k.startswith("_")})
                    return base
            except (OSError, json.JSONDecodeError):
                pass
        return _default_curator_state()

    def save_state(self, data: dict[str, Any]) -> None:
        _atomic_json_write(self.state_path, data)

    def is_enabled(self) -> bool:
        return bool(self.curator.enabled)

    def is_paused(self) -> bool:
        return bool(self.load_state().get("paused"))

    def set_paused(self, paused: bool) -> None:
        state = self.load_state()
        state["paused"] = bool(paused)
        self.save_state(state)

    def pin_note(self, path: str) -> None:
        state = self.load_state()
        pinned = list(state.get("pinned") or [])
        if path not in pinned:
            pinned.append(path)
        state["pinned"] = pinned
        self.save_state(state)

    def unpin_note(self, path: str) -> None:
        state = self.load_state()
        pinned = [p for p in (state.get("pinned") or []) if p != path]
        state["pinned"] = pinned
        self.save_state(state)

    def should_run_now(self, now: datetime | None = None) -> bool:
        if not self.is_enabled() or self.is_paused():
            return False
        state = self.load_state()
        last = _parse_iso(state.get("last_run_at"))
        if last is None:
            if now is None:
                now = _utc_now()
            state["last_run_at"] = now.isoformat()
            state["last_run_summary"] = (
                "deferred first run — seeded; use run_curator or wait one interval"
            )
            self.save_state(state)
            return False
        if now is None:
            now = _utc_now()
        return (now - last) >= timedelta(hours=self.curator.interval_hours)

    def maybe_run(self, dry_run: bool = False) -> CuratorResult | None:
        if not self.should_run_now():
            return None
        return self.run(dry_run=dry_run)

    def status(self) -> dict[str, Any]:
        state = self.load_state()
        usage = self.usage.load()
        note_usage = usage.get("notes", {})
        return {
            "enabled": self.is_enabled(),
            "paused": self.is_paused(),
            "interval_hours": self.curator.interval_hours,
            "stale_after_days": self.curator.stale_after_days,
            "archive_after_days": self.curator.archive_after_days,
            "compress_after_days": self.curator.compress_after_days,
            "compress_min_words": self.curator.compress_min_words,
            "pinned_count": len(state.get("pinned") or []),
            "pinned": state.get("pinned") or [],
            "last_run_at": state.get("last_run_at"),
            "last_run_summary": state.get("last_run_summary"),
            "last_report_path": state.get("last_report_path"),
            "run_count": state.get("run_count", 0),
            "tracked_notes": len(note_usage),
        }

    def _is_path_protected(self, rel: str) -> bool:
        from fnmatch import fnmatch

        for pattern in self.curator.protect_paths:
            if fnmatch(rel, pattern) or fnmatch(rel, pattern.lstrip("./")):
                return True
        return False

    def _is_pinned(self, rel: str, state: dict[str, Any]) -> bool:
        return rel in (state.get("pinned") or [])

    def _has_protect_marker(self, note: Note) -> bool:
        if PROTECT_FRONTMATTER.search(note.content):
            return True
        if PROTECT_TAGS.search(note.content):
            return True
        for tag in self.curator.protect_tags:
            if re.search(rf"#{re.escape(tag)}\b", note.content, re.IGNORECASE):
                return True
        return False

    def _has_success_marker(self, note: Note) -> bool:
        if SUCCESS_FRONTMATTER.search(note.content):
            return True
        if SUCCESS_BODY.search(note.content):
            return True
        return False

    def _is_invalid(self, note: Note) -> bool:
        if INVALID_FRONTMATTER.search(note.content):
            return True
        return bool(INVALID_TAGS.search(note.content))

    def _expires_at(self, note: Note) -> datetime | None:
        match = EXPIRES_AT_RE.search(note.content)
        if not match:
            return None
        return _parse_iso(match.group(1).strip())

    def _is_expired(self, note: Note, now: datetime) -> bool:
        expires = self._expires_at(note)
        return expires is not None and now >= expires

    def mark_invalid(self, path: str, reason: str = "") -> dict[str, Any]:
        self.unpin_note(path)
        fields: dict[str, Any] = {
            "status": "invalid",
            "validated": False,
            "functional": False,
            "invalidated_at": _utc_now().isoformat(),
        }
        if reason:
            fields["invalid_reason"] = reason
        note = set_note_fields(self.vault, path, fields)
        return {"ok": True, "path": path, "status": "invalid", "title": note.title}

    def set_expiry(self, path: str, expires_at: str) -> dict[str, Any]:
        parsed = _parse_iso(expires_at)
        if parsed is None:
            return {"ok": False, "error": f"invalid expires_at: {expires_at}"}
        note = set_note_fields(self.vault, path, {"expires_at": parsed.isoformat()})
        return {"ok": True, "path": path, "expires_at": parsed.isoformat(), "title": note.title}

    def delete_note(self, path: str) -> dict[str, Any]:
        """Archive note + purge indexes (recoverable). Overrides pin."""
        self.unpin_note(path)
        if not (self.vault / path).exists():
            return {"ok": False, "error": f"not found: {path}"}
        now = _utc_now()
        dest = self._archive_note(path, now, dry_run=False)
        self._purge_indexes(path, dry_run=False)
        return {"ok": True, "path": path, "archived_to": str(dest) if dest else None}

    def _word_count(self, text: str) -> int:
        return len(re.findall(r"\b\w+\b", text))

    def _days_since(self, dt: datetime | None, now: datetime) -> float:
        if dt is None:
            return float("inf")
        return (now - dt).total_seconds() / 86400.0

    def _anchor_datetime(self, note: Note, last_access: datetime | None) -> datetime:
        if last_access is not None:
            return last_access
        return datetime.fromtimestamp(note.mtime, tz=timezone.utc)

    def classify_note(
        self,
        note: Note,
        *,
        state: dict[str, Any],
        now: datetime,
    ) -> CuratorAction:
        rel = note.path

        if (
            ANTI_PATTERN_FRONTMATTER.search(note.content)
            or rel.startswith("Memory/Agent/Solutions/")
            or rel.startswith("Memory/Agent/Anti-Patterns/")
        ):
            return CuratorAction(rel, "protected", "agent solution or anti-pattern memory", 1)

        # Step 2 first — actively remove false / expired / spoiled data
        if self._is_invalid(note):
            reason = "status invalid / validated false / non-functional marker"
            return CuratorAction(rel, "archive", reason, 2)
        if self._is_expired(note, now):
            exp = self._expires_at(note)
            return CuratorAction(
                rel,
                "archive",
                f"expired at {exp.isoformat() if exp else 'unknown'}",
                2,
            )
        fm, _ = split_frontmatter(note.content)
        if rel.startswith("Memory/") and fm:
            spoil = spoil_status(fm, now)
            if spoil.get("unverified_stale"):
                return CuratorAction(
                    rel,
                    "archive",
                    f"spoiled metadata: {spoil.get('reason')} + no success verified_in 90d",
                    2,
                )

        # Step 1 — Question requirements
        if self._is_pinned(rel, state) or self._is_path_protected(rel):
            return CuratorAction(rel, "protected", "pinned or protected path", 1)
        if self._has_protect_marker(note):
            return CuratorAction(rel, "protected", "protect marker in note", 1)
        if self._has_success_marker(note):
            return CuratorAction(rel, "protected", "success/playbook/replicable marker", 1)

        last_access = self.usage.last_access(rel)
        anchor = self._anchor_datetime(note, last_access)
        idle_days = self._days_since(anchor, now)
        words = self._word_count(note.content)

        if idle_days >= self.curator.archive_after_days:
            return CuratorAction(
                rel,
                "archive",
                f"unused {idle_days:.0f}d (>= {self.curator.archive_after_days}d archive threshold)",
                2,
            )

        if (
            idle_days >= self.curator.compress_after_days
            and words >= self.curator.compress_min_words
            and "curator_compressed:" not in note.content
        ):
            return CuratorAction(
                rel,
                "compress",
                f"verbose ({words} words), unused {idle_days:.0f}d",
                3,
            )

        if idle_days >= self.curator.stale_after_days:
            return CuratorAction(
                rel,
                "refresh",
                f"stale {idle_days:.0f}d — touch mtime only, no mutation",
                4,
            )

        return CuratorAction(rel, "keep", "active or within thresholds", 4)

    def compress_content(self, content: str) -> str:
        """Step 3 — keep replicable structure, drop verbose prose."""
        preserved: list[str] = []
        for block in CODE_BLOCK.findall(content):
            preserved.append(block.strip())

        lines = content.splitlines()
        kept_lines: list[str] = []
        for line in lines:
            if HEADER_LINE.match(line) or BULLET_LINE.match(line):
                kept_lines.append(line)
            elif ACTION_LINE.search(line):
                kept_lines.append(line)
            elif SUCCESS_BODY.search(line):
                kept_lines.append(line)

        summary_lines = [l for l in kept_lines if l.strip()]
        if len(summary_lines) > 80:
            summary_lines = summary_lines[:80]
            summary_lines.append("…")

        header = (
            "---\n"
            "curator_compressed: true\n"
            f"curator_compressed_at: {_utc_now().isoformat()}\n"
            "---\n\n"
            "> Compressed by vault-memory curator (Elon step 3). "
            "Code blocks and replication cues preserved.\n\n"
        )
        body = "\n".join(summary_lines).strip()
        code_section = ""
        if preserved:
            code_section = "\n\n## Preserved code\n\n" + "\n\n".join(preserved[:12])
        compressed = header + body + code_section
        max_chars = self.curator.compress_max_chars
        if len(compressed) > max_chars:
            compressed = compressed[: max_chars - 20].rstrip() + "\n\n…(truncated)"
        return compressed

    def _archive_note(self, rel: str, now: datetime, dry_run: bool) -> Path | None:
        src = (self.vault / rel).resolve()
        if not src.exists():
            return None
        stamp = now.strftime("%Y-%m-%d")
        dest = self.archive_root / stamp / rel
        if dry_run:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        return dest

    def _purge_indexes(self, rel: str, dry_run: bool) -> None:
        if dry_run:
            return
        if self.graph:
            self.graph.delete_note(rel)

    def _touch_note(self, rel: str, dry_run: bool) -> None:
        if dry_run:
            return
        path = self.vault / rel
        if path.exists():
            path.touch()

    def run(self, *, dry_run: bool = False) -> CuratorResult:
        start = _utc_now()
        result = CuratorResult(dry_run=dry_run, started_at=start.isoformat())
        state = self.load_state()

        if not self.vault.exists():
            result.errors.append(f"Vault not found: {self.vault}")
            return result

        for rel in list_notes(self.vault, self.config.vault.ignore):
            result.scanned += 1
            try:
                note = read_note(self.vault, rel)
                action = self.classify_note(note, state=state, now=start)
                result.actions.append(action)

                if action.action == "keep":
                    result.kept += 1
                elif action.action == "protected":
                    result.protected += 1
                elif action.action == "refresh":
                    self._touch_note(rel, dry_run)
                    result.refreshed += 1
                elif action.action == "archive":
                    if not dry_run:
                        self._archive_note(rel, start, dry_run=False)
                        self._purge_indexes(rel, dry_run=False)
                    result.archived += 1
                elif action.action == "compress":
                    if not dry_run:
                        compressed = self.compress_content(note.content)
                        write_note(self.vault, rel, compressed)
                        if self.graph:
                            self.graph.upsert_note(read_note(self.vault, rel))
                    result.compressed += 1
                else:
                    result.skipped += 1
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"{rel}: {exc}")

        elapsed = (_utc_now() - start).total_seconds()
        result.duration_seconds = elapsed

        summary_parts = [
            f"scanned={result.scanned}",
            f"archived={result.archived}",
            f"compressed={result.compressed}",
            f"protected={result.protected}",
            f"refreshed={result.refreshed}",
        ]
        prefix = "dry-run: " if dry_run else ""
        summary = prefix + ", ".join(summary_parts)

        report_path = self._write_report(result, summary)
        if not dry_run:
            self._write_curator_log(result, summary, dry_run=False)
        if not dry_run:
            state = self.load_state()
            state["last_run_at"] = start.isoformat()
            state["last_run_duration_seconds"] = elapsed
            state["run_count"] = int(state.get("run_count", 0)) + 1
            state["last_run_summary"] = summary
            if report_path:
                state["last_report_path"] = str(report_path)
            self.save_state(state)
        else:
            state = self.load_state()
            state["last_run_summary"] = summary
            if report_path:
                state["last_report_path"] = str(report_path)
            self.save_state(state)

        return result

    def restore_archived(self, rel: str, *, stamp: str | None = None) -> dict[str, Any]:
        """Restore a note from archive/ back into the vault."""
        if stamp:
            src = self.archive_root / stamp / rel
        else:
            matches = sorted(self.archive_root.glob(f"*/{rel}"))
            if not matches:
                return {"ok": False, "error": f"not found in archive: {rel}"}
            src = matches[-1]

        if not src.exists():
            return {"ok": False, "error": f"archive missing: {src}"}

        dest = self.vault / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            return {"ok": False, "error": f"vault note already exists: {rel}"}

        shutil.move(str(src), str(dest))
        note = read_note(self.vault, rel)
        if self.graph:
            self.graph.upsert_note(note)
        return {"ok": True, "restored": rel, "from": str(src)}

    def _write_curator_log(self, result: CuratorResult, summary: str, *, dry_run: bool) -> None:
        """Append decisions to vault Memory/Curator-Logs/ for audit trail."""
        try:
            log_dir = self.vault / "Memory/Curator-Logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            day = (result.started_at or _utc_now().isoformat())[:10]
            log_path = log_dir / f"{day}.md"
            header = not log_path.exists()
            lines: list[str] = []
            if header:
                lines.extend(
                    [
                        "---",
                        "source: internal://vault-memory-curator",
                        "source_type: system",
                        f"added: {day}",
                        f"last_verified: {day}",
                        "verified_in: []",
                        "confidence: 1.0",
                        "spoil_after_days: 365",
                        "tags: [curator-log, system]",
                        "memory_policy: '[[Long-Term-Memory-Policy]]'",
                        "curator: pin",
                        "---",
                        "",
                        f"# Curator log {day}",
                        "",
                        "Audit trail for rule-based curation. Policy: [[Long-Term-Memory-Policy]].",
                        "",
                    ]
                )
            lines.append(f"## Run {result.started_at} (dry_run={dry_run})")
            lines.append(f"- {summary}")
            for action in result.actions:
                if action.action not in {"archive", "compress", "protected"}:
                    continue
                lines.append(f"- `{action.path}`: **{action.action}** — {action.reason}")
            lines.append("")
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
        except OSError:
            pass

    def _write_report(self, result: CuratorResult, summary: str) -> Path | None:
        try:
            self.reports_root.mkdir(parents=True, exist_ok=True)
            stamp = (result.started_at or _utc_now().isoformat()).replace(":", "-")[:19]
            run_dir = self.reports_root / stamp.replace("T", "-")
            suffix = 1
            while run_dir.exists():
                suffix += 1
                run_dir = self.reports_root / f"{stamp.replace('T', '-')}-{suffix}"
            run_dir.mkdir(parents=True, exist_ok=False)
            payload = result.to_dict()
            payload["summary"] = summary
            (run_dir / "run.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            lines = [
                f"# Vault curator run — {result.started_at}\n",
                f"Summary: {summary}\n",
                f"Dry run: {result.dry_run}\n",
                "## Elon steps applied\n",
                "- Step 1: Question requirements (protect pins/success/playbooks)",
                "- Step 2: Delete → archive stale unused notes",
                "- Step 3: Simplify → compress verbose notes",
                "- Step 4: Accelerate → incremental scan",
                "- Step 5: Automate → daemon/hooks/MCP\n",
                "## Actions\n",
            ]
            for action in result.actions:
                if action.action in {"archive", "compress"}:
                    lines.append(
                        f"- `{action.path}`: **{action.action}** (step {action.elon_step}) — {action.reason}"
                    )
            if result.errors:
                lines.append("\n## Errors\n")
                for err in result.errors:
                    lines.append(f"- {err}")
            lines.append("\n## Recovery\n")
            lines.append("- Restore: `curator_restore` MCP tool or move from `~/.vault-memory/archive/`")
            (run_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
            return run_dir
        except OSError:
            return None