"""LLM-powered handoff document synthesis."""

from __future__ import annotations

from kadmon.providers.base import LLMProvider, Message


HANDOFF_SYSTEM_PROMPT = """You are writing a task handoff for another agent taking over this work.
Write a focused task brief — what a senior dev would write for a colleague picking this up.

Include:
- One-line goal
- What's already done (with file paths)
- What to do next (specific, actionable)
- Key context pointers (files, decisions, gotchas)
- How to verify the work

Be as concise or detailed as the task requires. A simple bug fix needs 10 lines.
A complex refactor might need 60. Use your judgment — include what's needed to
continue effectively, nothing more.

Format as markdown with clear headers."""


class HandoffAgent:
    """Synthesizes a focused handoff document from session state."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    def synthesize(self, goal: str, completed: list[str], pending: list[str], session_events: list[dict]) -> str:
        """Generate a handoff doc from plan state and session log."""
        user_content = self._format_input(goal, completed, pending, session_events)
        messages = [Message(role="user", content=user_content)]
        response = self._provider.complete(messages, system=HANDOFF_SYSTEM_PROMPT)
        return response.content

    def _format_input(self, goal: str, completed: list[str], pending: list[str], session_events: list[dict]) -> str:
        """Format inputs for the LLM."""
        parts = [f"Goal: {goal}"]

        if completed:
            parts.append("\nCompleted steps:")
            for s in completed:
                parts.append(f"  - {s}")

        if pending:
            parts.append("\nRemaining steps:")
            for s in pending:
                parts.append(f"  - {s}")

        if session_events:
            parts.append("\nRecent session activity:")
            for e in session_events[-20:]:
                etype = e.get("event", "")
                data = e.get("data", {})
                if etype == "tool_executed":
                    status = "\u2713" if data.get("success") else "\u2717"
                    parts.append(f"  {status} {data.get('tool', '')}")
                elif etype == "step_completed":
                    parts.append(f"  Step {data.get('step_id', '')} {data.get('status', '')}")

        return "\n".join(parts)
