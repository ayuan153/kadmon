from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class StepStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    id: str
    description: str
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    max_attempts: int = 2
    notes: str = ""


@dataclass
class Plan:
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    revision_count: int = 0

    def current_step(self) -> PlanStep | None:
        for step in self.steps:
            if step.status in (StepStatus.PENDING, StepStatus.ACTIVE):
                return step
        return None

    def is_complete(self) -> bool:
        return all(
            s.status in (StepStatus.DONE, StepStatus.SKIPPED, StepStatus.FAILED) for s in self.steps
        )

    def mark_active(self, step_id: str):
        step = self._get(step_id)
        if step:
            step.status = StepStatus.ACTIVE

    def mark_done(self, step_id: str, notes: str = ""):
        step = self._get(step_id)
        if step:
            step.status = StepStatus.DONE
            if notes:
                step.notes = notes

    def mark_failed(self, step_id: str, notes: str = ""):
        step = self._get(step_id)
        if step:
            step.status = StepStatus.FAILED
            step.attempts += 1
            if notes:
                step.notes = notes

    def add_step_after(self, after_id: str, new_step: PlanStep):
        for i, s in enumerate(self.steps):
            if s.id == after_id:
                self.steps.insert(i + 1, new_step)
                return
        self.steps.append(new_step)

    def to_prompt(self) -> str:
        """Format plan for injection into LLM context."""
        lines = [f"Plan: {self.goal}", ""]
        for s in self.steps:
            marker = {
                "pending": "[ ]",
                "active": "[>]",
                "done": "[x]",
                "failed": "[!]",
                "skipped": "[-]",
            }[s.status.value]
            lines.append(f"  {marker} {s.id}. {s.description}")
            if s.notes:
                lines.append(f"       Note: {s.notes}")
        return "\n".join(lines)

    def _get(self, step_id: str) -> PlanStep | None:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def steps_since_revision(self) -> int:
        done_count = sum(1 for s in self.steps if s.status == StepStatus.DONE)
        return done_count  # Simple proxy
