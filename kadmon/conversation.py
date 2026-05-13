from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ConversationTurn:
    turn_id: int
    prompt: str
    timestamp: float
    context: list
    plan: dict | None


class ConversationHistory:
    """Manages conversation snapshots for user-facing rewind."""

    def __init__(self, repo_root: str, max_turns: int = 10):
        self._dir = Path(repo_root) / ".kadmon" / "conversation"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max = max_turns
        self._seq = self._next_seq()

    def snapshot(self, prompt: str, context: list, plan: dict | None = None) -> int:
        """Save conversation state before processing a prompt. Returns turn_id."""
        turn_id = self._seq
        turn = ConversationTurn(
            turn_id=turn_id,
            prompt=prompt,
            timestamp=time.time(),
            context=context,
            plan=plan,
        )
        path = self._dir / f"turn_{turn_id:03d}.json"
        path.write_text(json.dumps(asdict(turn), default=str))
        self._seq += 1
        self._prune()
        return turn_id

    def rewind(self, turn_id: int) -> ConversationTurn | None:
        """Load conversation state from a specific turn."""
        path = self._dir / f"turn_{turn_id:03d}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        for f in sorted(self._dir.glob("turn_*.json")):
            fid = int(f.stem.split("_")[1])
            if fid > turn_id:
                f.unlink()
        self._seq = turn_id + 1
        return ConversationTurn(**data)

    def list_turns(self) -> list[dict]:
        """Return recent turns (turn_id + prompt), newest first."""
        turns = []
        for f in sorted(self._dir.glob("turn_*.json"), reverse=True):
            data = json.loads(f.read_text())
            turns.append({"turn_id": data["turn_id"], "prompt": data["prompt"][:100]})
        return turns

    def clear(self) -> None:
        """Delete all conversation snapshots."""
        for f in self._dir.glob("turn_*.json"):
            f.unlink()
        self._seq = 1

    def _prune(self) -> None:
        """Keep only the last max_turns snapshots."""
        files = sorted(self._dir.glob("turn_*.json"))
        while len(files) > self._max:
            files.pop(0).unlink()

    def _next_seq(self) -> int:
        files = list(self._dir.glob("turn_*.json"))
        if not files:
            return 1
        ids = [int(f.stem.split("_")[1]) for f in files]
        return max(ids) + 1
