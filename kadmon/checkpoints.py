from __future__ import annotations

import json
import shutil
import time
from pathlib import Path


class CheckpointManager:
    """File-level checkpoints for rollback on edit failure."""

    def __init__(self, repo_root: str, max_checkpoints: int = 20):
        self._root = Path(repo_root).resolve()
        self._dir = self._root / ".kadmon" / "checkpoints"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max = max_checkpoints
        self._seq = self._next_seq()

    def create(self, files: list[str], tool: str) -> str:
        """Snapshot current content of files before edit. Returns checkpoint_id."""
        existing = [f for f in files if (self._root / f).is_file()]
        if not existing:
            return ""

        checkpoint_id = f"{self._seq:04d}"
        cp_dir = self._dir / checkpoint_id / "files"
        cp_dir.mkdir(parents=True, exist_ok=True)

        for rel_path in existing:
            src = self._root / rel_path
            dest = cp_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

        meta = {"id": checkpoint_id, "timestamp": time.time(), "tool": tool, "files": existing}
        (self._dir / checkpoint_id / "meta.json").write_text(json.dumps(meta))

        self._seq += 1
        self._prune()
        return checkpoint_id

    def rollback(self, checkpoint_id: str | None = None) -> list[str]:
        """Restore files from checkpoint. Returns list of restored paths."""
        if checkpoint_id is None:
            checkpoint_id = self._latest_id()
        if not checkpoint_id:
            return []

        cp_dir = self._dir / checkpoint_id
        if not cp_dir.exists():
            return []

        meta = json.loads((cp_dir / "meta.json").read_text())
        restored = []
        for rel_path in meta["files"]:
            src = cp_dir / "files" / rel_path
            if src.exists():
                dest = self._root / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                restored.append(rel_path)
        return restored

    def list(self) -> list[dict]:
        """Return metadata for all checkpoints, newest first."""
        checkpoints = []
        for cp_dir in sorted(self._dir.iterdir(), reverse=True):
            meta_path = cp_dir / "meta.json"
            if meta_path.exists():
                checkpoints.append(json.loads(meta_path.read_text()))
        return checkpoints

    def clear(self) -> None:
        """Delete all checkpoints."""
        if self._dir.exists():
            shutil.rmtree(self._dir)
            self._dir.mkdir(parents=True, exist_ok=True)
        self._seq = 1

    def _prune(self) -> None:
        """Remove oldest checkpoints beyond max."""
        dirs = sorted(d for d in self._dir.iterdir() if d.is_dir())
        while len(dirs) > self._max:
            shutil.rmtree(dirs.pop(0))

    def _next_seq(self) -> int:
        """Find next sequence number."""
        existing = [d.name for d in self._dir.iterdir() if d.is_dir()]
        if not existing:
            return 1
        return max(int(n) for n in existing if n.isdigit()) + 1

    def _latest_id(self) -> str:
        """Get the most recent checkpoint ID."""
        dirs = sorted(d.name for d in self._dir.iterdir() if d.is_dir() and d.name.isdigit())
        return dirs[-1] if dirs else ""
