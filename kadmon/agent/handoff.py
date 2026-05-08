"""Autonomous handoff: detect context degradation and reset with continuity."""

import time
from dataclasses import dataclass
from pathlib import Path

from kadmon.agent.context import ContextManager
from kadmon.agent.planner import Plan, StepStatus


@dataclass
class HandoffTrigger:
    """Why a handoff was triggered."""

    reason: str  # token_budget | task_boundary | quality_degradation
    details: str = ""


class HandoffMonitor:
    """Detects when the agent should hand off to a fresh context."""

    def __init__(
        self,
        context_threshold: float = 0.8,
        loop_threshold: int = 5,
    ):
        self.context_threshold = context_threshold
        self.loop_threshold = loop_threshold
        self._loop_recovery_count = 0

    def check(self, context: ContextManager, plan: Plan | None = None) -> HandoffTrigger | None:
        """Check if handoff should trigger. Returns trigger reason or None."""
        # 1. Token budget: context is getting too full
        if context.utilization > self.context_threshold:
            return HandoffTrigger(
                reason="token_budget",
                details=f"Context at {context.utilization:.0%} capacity",
            )

        # 2. Task boundary: current plan is complete
        if plan and plan.is_complete():
            return HandoffTrigger(
                reason="task_boundary",
                details="Current plan completed",
            )

        # 3. Quality degradation: too many loop recoveries
        if self._loop_recovery_count >= self.loop_threshold:
            return HandoffTrigger(
                reason="quality_degradation",
                details=f"Loop recovery fired {self._loop_recovery_count} times",
            )

        return None

    def record_loop_recovery(self):
        """Called when the loop detector fires a recovery message."""
        self._loop_recovery_count += 1

    def reset(self):
        self._loop_recovery_count = 0


class HandoffManager:
    """Orchestrates the handoff: save state, craft doc, reset context, resume."""

    def __init__(self, repo_root: str, librarian=None, session_tracker=None):
        self.repo_root = repo_root
        self.librarian = librarian
        self.session_tracker = session_tracker
        self.handoffs_dir = Path(repo_root) / ".kadmon" / "handoffs"
        self.handoffs_dir.mkdir(parents=True, exist_ok=True)
        (self.handoffs_dir / "history").mkdir(exist_ok=True)

    def execute(self, context: ContextManager, plan: Plan | None, trigger: HandoffTrigger) -> str:
        """Execute a handoff. Returns the handoff document to inject into fresh context."""
        # 1. Craft handoff document
        handoff_doc = self._craft_handoff(plan, trigger)

        # 2. Save to library
        if self.librarian and plan:
            self.librarian.save_task_context(plan.goal, handoff_doc)

        # 3. Save handoff file
        self._save_handoff(handoff_doc)

        # 4. Mark session as handed off
        if self.session_tracker:
            self.session_tracker.mark_handed_off()

        # 5. Reset context
        context.messages.clear()
        context._token_estimate = 0

        # 6. Build fresh context from library + handoff
        cold_start = ""
        if self.librarian:
            cold_start = self.librarian.get_cold_start_context()

        resume_prompt = self._build_resume_prompt(cold_start, handoff_doc)
        return resume_prompt

    def _craft_handoff(self, plan: Plan | None, trigger: HandoffTrigger) -> str:
        """Generate the handoff document."""
        timestamp = time.strftime("%Y-%m-%d %H:%M")
        sections = [
            f"# Handoff — {timestamp}",
            f"\nReason: {trigger.reason} ({trigger.details})",
        ]

        if plan:
            # Accomplished
            done = [s for s in plan.steps if s.status == StepStatus.DONE]
            if done:
                sections.append("\n## Accomplished")
                for s in done:
                    sections.append(f"- {s.description}")
                    if s.notes:
                        sections.append(f"  Note: {s.notes}")

            # In progress
            active = [s for s in plan.steps if s.status == StepStatus.ACTIVE]
            if active:
                sections.append("\n## In Progress")
                for s in active:
                    sections.append(f"- {s.description}")

            # Remaining
            pending = [s for s in plan.steps if s.status == StepStatus.PENDING]
            if pending:
                sections.append("\n## Remaining Plan")
                for s in pending:
                    sections.append(f"- [ ] {s.description}")

            sections.append(f"\n## Goal\n\n{plan.goal}")
        else:
            sections.append("\n## Note\n\nNo structured plan was active at handoff time.")

        return "\n".join(sections)

    def _save_handoff(self, handoff_doc: str):
        """Save handoff to latest.md and history/."""
        # Save as latest
        (self.handoffs_dir / "latest.md").write_text(handoff_doc)
        # Save to history
        timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
        (self.handoffs_dir / "history" / f"{timestamp}.md").write_text(handoff_doc)

    def _build_resume_prompt(self, cold_start: str, handoff_doc: str) -> str:
        """Build the prompt that starts the fresh context."""
        parts = []
        if cold_start:
            parts.append(cold_start)
        parts.append("# Handoff Context\n\n" + handoff_doc)
        parts.append(
            "\nYou are resuming work after a context handoff. "
            "Continue from where the previous session left off. "
            "Focus on the remaining plan steps."
        )
        return "\n\n---\n\n".join(parts)
