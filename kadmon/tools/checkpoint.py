from __future__ import annotations

from kadmon.checkpoints import CheckpointManager
from kadmon.tools.base import Tool, ToolResult


class CheckpointRollbackTool(Tool):
    name = "checkpoint_rollback"
    description = "Roll back file changes to a previous checkpoint. Use when an edit caused test failures and you want to undo it."
    parameters = {
        "type": "object",
        "properties": {
            "checkpoint_id": {
                "type": "string",
                "description": "Checkpoint ID to rollback to (omit for most recent)",
            },
        },
        "required": [],
    }

    def __init__(self, checkpoint_manager: CheckpointManager):
        self._manager = checkpoint_manager

    def execute(self, checkpoint_id: str | None = None, **kwargs) -> ToolResult:
        restored = self._manager.rollback(checkpoint_id)
        if not restored:
            return ToolResult(output="No checkpoint to rollback to.", error=True)
        return ToolResult(output=f"Rolled back {len(restored)} file(s): {', '.join(restored)}")
