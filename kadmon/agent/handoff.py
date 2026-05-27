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

        # 2. Clean break: plan complete + context is substantial (not a trivial task)
        # Only triggers when there's been meaningful work (context > 40% used),
        # indicating the agent should offer a handoff rather than continuing to accumulate.
        if plan and plan.is_complete() and context.utilization > 0.4:
            return HandoffTrigger(
                reason="clean_break",
                details="Plan completed with substantial context — natural handoff point",
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

    def __init__(self, repo_root: str, librarian=None, session_tracker=None, provider=None):
        self.repo_root = repo_root
        self.librarian = librarian
        self.session_tracker = session_tracker
        self._provider = provider
        self.handoffs_dir = Path(repo_root) / "docs" / "handoffs"
        self.handoffs_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, context: ContextManager, plan: Plan | None, trigger: HandoffTrigger) -> str:
        """Execute a handoff. Returns the handoff document to inject into fresh context."""
        from kadmon.agent.pruner import Pruner

        pruner = Pruner()

        # 0. Prune library (archive old task if pivoting)
        if self.librarian:
            new_task = plan.goal if plan else ""
            pruner.prune_library(self.librarian.library_path, new_task)

        # 1. Craft handoff document (uses pruner for concise summary)
        handoff_doc = self._craft_handoff(plan, trigger, pruner)

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

        # 6. Build resume prompt (handoff doc only — no blob injection)
        resume_prompt = self._build_resume_prompt("", handoff_doc)
        return resume_prompt

    def _craft_handoff(self, plan: Plan | None, trigger: HandoffTrigger, pruner=None) -> str:
        """Generate the handoff document via HandoffAgent or fallback."""
        if self._provider and plan:
            from kadmon.memory.agents.handoff_agent import HandoffAgent
            from kadmon.memory.session_log import SessionLogger

            agent = HandoffAgent(self._provider)
            completed = [s.description + (f" ({s.notes})" if s.notes else "") for s in plan.steps if s.status == StepStatus.DONE]
            pending = [s.description for s in plan.steps if s.status in (StepStatus.PENDING, StepStatus.ACTIVE)]
            session_events = SessionLogger(self.repo_root).read_events()
            return agent.synthesize(plan.goal, completed, pending, session_events)

        # Fallback: mechanical format (no provider available)
        timestamp = time.strftime("%Y-%m-%d %H:%M")
        sections = [f"# Handoff — {timestamp}", f"\nReason: {trigger.reason} ({trigger.details})"]
        if plan:
            done = [s for s in plan.steps if s.status == StepStatus.DONE]
            if done:
                sections.append("\n## Accomplished")
                for s in done:
                    sections.append(f"- {s.description}")
                    if s.notes:
                        sections.append(f"  Note: {s.notes}")
            active = [s for s in plan.steps if s.status == StepStatus.ACTIVE]
            if active:
                sections.append("\n## In Progress")
                for s in active:
                    sections.append(f"- {s.description}")
            pending = [s for s in plan.steps if s.status == StepStatus.PENDING]
            if pending:
                sections.append("\n## Remaining Plan")
                for s in pending:
                    sections.append(f"- {s.description}")
            sections.append(f"\n## Goal\n\n{plan.goal}")
        else:
            sections.append("\n## Note\n\nNo structured plan was active at handoff time.")
        return "\n".join(sections)

    def _save_handoff(self, handoff_doc: str):
        """Save handoff to docs/handoffs/latest.md (committed, not gitignored)."""
        self.handoffs_dir.mkdir(parents=True, exist_ok=True)
        (self.handoffs_dir / "latest.md").write_text(handoff_doc)

    def _build_resume_prompt(self, cold_start: str, handoff_doc: str) -> str:
        """Build the prompt that starts the fresh context."""
        return (
            handoff_doc + "\n\n---\n\n"
            "You are resuming work after a context handoff. "
            "The above is your task brief. Continue from where the previous session left off. "
            "Use library_read if you need project background. Use verify to check your work."
        )

