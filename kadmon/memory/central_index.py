"""Central session index for cross-project discovery."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class IndexEntry:
    session_key: str
    repo: str
    task: str
    started: str
    last_updated: str
    status: str = "in_progress"  # in_progress | completed | handed_off
    files_touched: list[str] = field(default_factory=list)


class CentralIndex:
    """Manages ~/.kadmon/sessions/index.json for cross-project session discovery."""

    def __init__(self):
        self._index_dir = Path.home() / ".kadmon" / "sessions"
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._index_dir / "index.json"

    def add_entry(self, session_key: str, repo: str, task: str) -> None:
        """Add a new session entry to the index."""
        entries = self._load()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        entry = IndexEntry(
            session_key=session_key,
            repo=repo,
            task=task,
            started=now,
            last_updated=now,
        )
        entries[session_key] = asdict(entry)
        self._save(entries)

    def update_entry(self, session_key: str, status: str, files_touched: list[str] | None = None) -> None:
        """Update an existing entry's status and timestamp."""
        entries = self._load()
        if session_key not in entries:
            return
        entries[session_key]["status"] = status
        entries[session_key]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if files_touched:
            entries[session_key]["files_touched"] = files_touched
        self._save(entries)

    def find_by_repo(self, repo: str) -> IndexEntry | None:
        """Find the most recent session for a given repo path."""
        entries = self._load()
        matches = [e for e in entries.values() if e.get("repo") == repo]
        if not matches:
            return None
        matches.sort(key=lambda e: e.get("last_updated", ""), reverse=True)
        m = matches[0]
        return IndexEntry(**{k: m[k] for k in IndexEntry.__dataclass_fields__ if k in m})

    def list_recent(self, days: int = 14) -> list[IndexEntry]:
        """List sessions from the last N days across all projects."""
        entries = self._load()
        cutoff = time.time() - (days * 86400)
        recent = []
        for e in entries.values():
            try:
                updated = time.mktime(time.strptime(e.get("last_updated", ""), "%Y-%m-%dT%H:%M:%SZ"))
                if updated >= cutoff:
                    recent.append(IndexEntry(**{k: e[k] for k in IndexEntry.__dataclass_fields__ if k in e}))
            except (ValueError, KeyError):
                continue
        recent.sort(key=lambda x: x.last_updated, reverse=True)
        return recent

    def _load(self) -> dict:
        """Load index from disk."""
        if not self._index_path.exists():
            return {}
        try:
            return json.loads(self._index_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, entries: dict) -> None:
        """Write index to disk."""
        self._index_path.write_text(json.dumps(entries, indent=2) + "\n")
