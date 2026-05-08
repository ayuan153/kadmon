"""Session tracking with delegation status."""

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Delegation:
    id: str
    agent: str
    task: str
    status: str = "in_progress"  # in_progress | completed | failed
    started: str = ""
    completed: str | None = None
    summary: str | None = None


@dataclass
class Session:
    session_id: str = ""
    started: str = ""
    task: str = ""
    status: str = "in_progress"  # in_progress | completed | handed_off
    delegations: list[Delegation] = field(default_factory=list)


class SessionTracker:
    """Tracks active session state in .kadmon/session.json."""

    def __init__(self, repo_root: str):
        self.kadmon_dir = Path(repo_root) / ".kadmon"
        self.kadmon_dir.mkdir(parents=True, exist_ok=True)
        self.session_path = self.kadmon_dir / "session.json"
        self.sessions_dir = self.kadmon_dir / "sessions"
        self.sessions_dir.mkdir(exist_ok=True)
        self._session: Session | None = None

    def start(self, task: str) -> Session:
        """Start a new session. Archives any existing session first."""
        if self._session and self.session_path.exists():
            self._archive_session()

        self._session = Session(
            session_id=uuid.uuid4().hex[:8],
            started=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            task=task,
        )
        self._save()
        return self._session

    def load(self) -> Session | None:
        """Load existing session from disk. Returns None if no active session."""
        if not self.session_path.exists():
            return None
        try:
            data = json.loads(self.session_path.read_text())
            delegations = [Delegation(**d) for d in data.get("delegations", [])]
            self._session = Session(
                session_id=data.get("session_id", ""),
                started=data.get("started", ""),
                task=data.get("task", ""),
                status=data.get("status", "in_progress"),
                delegations=delegations,
            )
            return self._session
        except (json.JSONDecodeError, KeyError):
            return None

    def start_delegation(self, delegation_id: str, agent: str, task: str):
        """Record a delegation starting."""
        if not self._session:
            return
        d = Delegation(
            id=delegation_id,
            agent=agent,
            task=task,
            started=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self._session.delegations.append(d)
        self._save()

    def complete_delegation(self, delegation_id: str, summary: str):
        """Mark a delegation as completed."""
        if not self._session:
            return
        for d in self._session.delegations:
            if d.id == delegation_id:
                d.status = "completed"
                d.completed = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                d.summary = summary
                break
        self._save()

    def fail_delegation(self, delegation_id: str, summary: str):
        """Mark a delegation as failed."""
        if not self._session:
            return
        for d in self._session.delegations:
            if d.id == delegation_id:
                d.status = "failed"
                d.completed = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                d.summary = summary
                break
        self._save()

    def complete_session(self):
        """Mark the session as completed and archive it."""
        if self._session:
            self._session.status = "completed"
            self._save()
            self._archive_session()

    def mark_handed_off(self):
        """Mark session as handed off (context reset, continuing in new session)."""
        if self._session:
            self._session.status = "handed_off"
            self._save()
            self._archive_session()

    def get_interrupted_delegations(self) -> list[Delegation]:
        """Get delegations that were in_progress (interrupted by crash)."""
        if not self._session:
            return []
        return [d for d in self._session.delegations if d.status == "in_progress"]

    def get_completed_delegations(self) -> list[Delegation]:
        """Get completed delegations (don't re-dispatch these)."""
        if not self._session:
            return []
        return [d for d in self._session.delegations if d.status == "completed"]

    def _save(self):
        """Write session state to disk."""
        if not self._session:
            return
        data = {
            "session_id": self._session.session_id,
            "started": self._session.started,
            "task": self._session.task,
            "status": self._session.status,
            "delegations": [asdict(d) for d in self._session.delegations],
        }
        self.session_path.write_text(json.dumps(data, indent=2))

    def _archive_session(self):
        """Move current session to sessions/ history."""
        if self.session_path.exists() and self._session:
            dest = self.sessions_dir / f"{self._session.session_id}.json"
            dest.write_text(self.session_path.read_text())
            self.session_path.unlink()
        self._session = None
