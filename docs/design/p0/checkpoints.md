# Checkpoints

## Overview

Checkpoints provide file-level rollback independent of the user's git history. Before each file edit, the agent snapshots the original file content. If an edit breaks things, the agent (or user) can rollback to any prior checkpoint without touching git.

## Architecture

```
.kadmon/checkpoints/
├── 0001/
│   ├── meta.json          # {"id": "0001", "ts": "...", "tool_call": "edit_file", "files": ["src/foo.py"]}
│   └── files/
│       └── src/foo.py     # Content BEFORE the edit
├── 0002/
│   ├── meta.json
│   └── files/
│       └── src/bar.py
```

- Sequence-numbered directories (zero-padded, monotonic within session)
- `files/` mirrors project-relative paths of snapshotted files
- Only files about to be modified are stored — never unchanged files

## Implementation

### CheckpointManager (`kadmon/checkpoints.py`)

```python
class CheckpointManager:
    def __init__(self, project_root: Path, max_checkpoints: int = 20): ...
    def create(self, files: list[Path], tool_call: str) -> str:
        """Snapshot current content of `files`. Returns checkpoint_id."""
    def rollback(self, checkpoint_id: str) -> list[Path]:
        """Restore all files from checkpoint to their pre-edit state. Returns restored paths."""
    def list(self) -> list[dict]:
        """Return metadata for all checkpoints, newest first."""
    def clear(self) -> None:
        """Delete all checkpoints (called on session start)."""
    def _prune(self) -> None:
        """Remove oldest checkpoints beyond max_checkpoints."""
```

### Tool integration

`WriteFileTool` and `EditFileTool` call `checkpoint_manager.create([target_path], tool_call=self.name)` before performing any write. No checkpoint is created if the file doesn't exist yet (nothing to rollback to).

### New tool: `checkpoint_rollback`

Available to the agent in the tool list. Schema:

```python
class CheckpointRollbackTool:
    """Roll back to a previous checkpoint. Use when an edit caused test failures."""
    def run(self, checkpoint_id: str | None = None) -> str:
        # None → rollback most recent checkpoint
```

## Rollback Semantics

- Restores ALL files in the checkpoint to their saved (pre-edit) content
- Does NOT unstage git changes, create commits, or modify `.git/`
- Agent workflow: edit → test → fail → `checkpoint_rollback` → try different approach
- Rolling back checkpoint N does not delete checkpoints N+1, N+2... (they remain valid)

## What We Don't Do

- **No shadow git** — avoids stash conflicts, index corruption, submodule issues
- **No snapshotting unchanged files** — only files about to be written
- **No cross-session persistence** — `CheckpointManager.clear()` runs on session start

## UX

| Actor | Interface |
|-------|-----------|
| Agent | `checkpoint_rollback` tool (autonomous, no human approval needed) |
| User  | `kadmon rollback [checkpoint_id]` CLI command |
| User  | `kadmon checkpoints` to list available checkpoints |

## Success Criteria

1. Agent can recover from a bad edit without human intervention
2. User's git status/log is never affected by checkpoint operations
3. Storage is bounded (max 20 checkpoints, pruned automatically)
4. Zero overhead for new-file creation (no snapshot needed)
5. Session restart starts clean — no stale checkpoint state
