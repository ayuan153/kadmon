from kadmon.agent.checkpoint import CheckpointManager
from kadmon.agent.planner import Plan, PlanStep
from kadmon.agent.recovery import LoopDetector


class BacktrackManager:
    """Plan-aware backtracking with git checkpoints."""

    def __init__(self, checkpoint_mgr: CheckpointManager, max_backtracks: int = 3):
        self.checkpoint = checkpoint_mgr
        self.loop_detector = LoopDetector(threshold=3)
        self.max_backtracks = max_backtracks
        self._backtrack_count = 0

    def on_step_start(self, step: PlanStep):
        """Called when a plan step begins. Saves a checkpoint."""
        self.checkpoint.save(label=f"step-{step.id}: {step.description[:50]}")
        self.loop_detector.reset()

    def on_tool_result(
        self, tool_name: str, args: dict, error: bool, error_msg: str = ""
    ) -> str | None:
        """Called after each tool execution. Returns recovery message if needed."""
        loop_action = self.loop_detector.record_action(tool_name, args)
        loop_error = False
        if error:
            loop_error = self.loop_detector.record_error(error_msg)

        if loop_action or loop_error:
            return self.loop_detector.get_recovery_message()
        return None

    def should_backtrack(self, plan: Plan) -> bool:
        """Check if we should backtrack the current step."""
        step = plan.current_step()
        if not step:
            return False
        return step.attempts >= step.max_attempts

    def backtrack(self, plan: Plan) -> str:
        """Perform backtracking: restore checkpoint, mark step failed, suggest alternative."""
        if self._backtrack_count >= self.max_backtracks:
            return (
                "Maximum backtracks reached. Submitting best attempt. "
                "Consider a fundamentally different approach."
            )

        step = plan.current_step()
        if not step:
            return "No active step to backtrack."

        # Mark current step as failed
        plan.mark_failed(step.id, notes=f"Failed after {step.attempts} attempts, backtracking")

        # Restore to checkpoint
        if self.checkpoint.has_checkpoints:
            self.checkpoint.restore()

        self._backtrack_count += 1
        self.loop_detector.reset()

        return (
            f'BACKTRACK: Step {step.id} ("{step.description}") failed after '
            f"{step.attempts} attempts. "
            f"Code reverted to checkpoint. "
            f"Try a completely different approach. "
            f"Backtracks remaining: {self.max_backtracks - self._backtrack_count}"
        )

    @property
    def backtracks_remaining(self) -> int:
        return self.max_backtracks - self._backtrack_count
