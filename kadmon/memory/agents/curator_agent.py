from __future__ import annotations

from pathlib import Path

from kadmon.memory.agents.write_agent import WriteAgent
from kadmon.memory.agents.prune_agent import PruneAgent
from kadmon.memory.session_log import SessionLogger
from kadmon.memory.token_tracker import TokenTracker
from kadmon.providers.base import LLMProvider, Message


CURATOR_SYSTEM_PROMPT = """You are the Library Curator agent. Your job is to extract key learnings from a session log.

Given a sequence of session events (tool calls, plan steps, outcomes), extract the important knowledge worth preserving:
- Architecture decisions made
- Patterns discovered
- Conventions established
- Gotchas encountered
- Key file paths and their purposes

Respond in this format:
TOPIC: <category (architecture, conventions, decisions, or a custom topic)>
CONTENT: <the learning, concise and actionable>

You may output multiple TOPIC/CONTENT pairs separated by blank lines. If the session has nothing worth preserving (e.g., just a simple question/answer), respond with: NOTHING"""


class CuratorAgent:
    """Compresses session logs into library knowledge."""

    def __init__(self, provider: LLMProvider, repo_root: str):
        self._provider = provider
        self._library_path = Path(repo_root) / ".kadmon" / "library"
        self._logger = SessionLogger(repo_root)
        self._write_agent = WriteAgent(provider, self._library_path)
        self._prune_agent = PruneAgent(provider, self._library_path)
        self.tracker = TokenTracker()

    def curate(self) -> str:
        """Compress session log into library knowledge. Returns summary."""
        events = self._logger.read_events()
        if not events:
            return "No session log to curate."

        learnings = self._extract_learnings(events)
        if not learnings:
            self._logger.clear()
            return "Session curated — nothing worth preserving."

        for topic, content in learnings:
            self._write_agent.update(topic, content, tracker=self.tracker)

        task = self._extract_task(events)
        self._prune_agent.prune(task, tracker=self.tracker)

        self._logger.clear()
        return f"Session curated — {len(learnings)} learning(s) saved to library."

    def _extract_learnings(self, events: list[dict]) -> list[tuple[str, str]]:
        """One LLM call to extract learnings from raw events."""
        summary = self._format_events(events)
        messages = [Message(role="user", content=summary)]
        response = self._provider.complete(messages, system=CURATOR_SYSTEM_PROMPT)
        if self.tracker:
            self.tracker.record(response.usage.input_tokens, response.usage.output_tokens)
        return self._parse_learnings(response.content)

    def _format_events(self, events: list[dict]) -> str:
        """Format events into a concise summary for the LLM."""
        lines: list[str] = []
        for e in events:
            etype = e.get("event", "")
            data = e.get("data", {})
            if etype == "session_start":
                lines.append(f"Task: {data.get('task', '')}")
            elif etype == "plan_created":
                lines.append(f"Plan: {data.get('goal', '')}")
                for s in data.get("steps", []):
                    lines.append(f"  - {s}")
            elif etype == "step_completed":
                lines.append(f"Step {data.get('step_id', '')} {data.get('status', '')}: {data.get('notes', '')}")
            elif etype == "tool_executed":
                status = "✓" if data.get("success") else "✗"
                args = data.get("args", {})
                lines.append(f"{status} {data.get('tool', '')}({', '.join(f'{k}={v}' for k, v in args.items())})")
            elif etype == "session_end":
                lines.append(f"Session ended: {data.get('status', '')}")
        return "\n".join(lines)

    def _parse_learnings(self, content: str) -> list[tuple[str, str]]:
        """Parse TOPIC/CONTENT pairs from LLM response."""
        if "NOTHING" in content.strip():
            return []
        learnings: list[tuple[str, str]] = []
        current_topic = ""
        current_content = ""
        for line in content.splitlines():
            if line.startswith("TOPIC:"):
                if current_topic and current_content:
                    learnings.append((current_topic.strip(), current_content.strip()))
                current_topic = line[len("TOPIC:"):].strip()
                current_content = ""
            elif line.startswith("CONTENT:"):
                current_content = line[len("CONTENT:"):].strip()
            elif current_content:
                current_content += "\n" + line
        if current_topic and current_content:
            learnings.append((current_topic.strip(), current_content.strip()))
        return learnings

    def _extract_task(self, events: list[dict]) -> str:
        """Get the task from session_start event."""
        for e in events:
            if e.get("event") == "session_start":
                return e.get("data", {}).get("task", "")
        return ""
