from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class EventType(str, Enum):
    SESSION_START = "session_start"
    PLAN_CREATED = "plan_created"
    STEP_COMPLETED = "step_completed"
    TOOL_EXECUTED = "tool_executed"
    SESSION_END = "session_end"


@dataclass
class LogEvent:
    event: EventType
    timestamp: float
    data: dict


class SessionLogger:
    """Append-only JSONL logger for session events."""

    def __init__(self, repo_root: str):
        self._log_path = Path(repo_root) / ".kadmon" / "sessions" / "log.jsonl"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: EventType, **data) -> None:
        """Append a structured event to the session log."""
        entry = LogEvent(event=event_type, timestamp=time.time(), data=data)
        with open(self._log_path, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def session_start(self, task: str) -> None:
        self.append(EventType.SESSION_START, task=task)

    def session_end(self, status: str) -> None:
        self.append(EventType.SESSION_END, status=status)

    def plan_created(self, goal: str, steps: list[str]) -> None:
        self.append(EventType.PLAN_CREATED, goal=goal, steps=steps)

    def step_completed(self, step_id: str, status: str, notes: str = "") -> None:
        self.append(EventType.STEP_COMPLETED, step_id=step_id, status=status, notes=notes)

    def tool_executed(self, tool_name: str, args: dict, success: bool) -> None:
        # Truncate large args to keep log manageable
        safe_args = {k: str(v)[:200] for k, v in args.items()}
        self.append(EventType.TOOL_EXECUTED, tool=tool_name, args=safe_args, success=success)

    def read_events(self) -> list[dict]:
        """Read all events from the log. Used by Curator Agent later."""
        if not self._log_path.exists():
            return []
        events = []
        for line in self._log_path.read_text().splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    def clear(self) -> None:
        """Clear the log (after curation)."""
        if self._log_path.exists():
            self._log_path.unlink()
