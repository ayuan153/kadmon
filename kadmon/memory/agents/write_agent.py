from __future__ import annotations

from datetime import date
from pathlib import Path

from kadmon.memory.token_tracker import TokenTracker
from kadmon.providers.base import LLMProvider, Message


WRITE_SYSTEM_PROMPT = """You are the Library Write agent. Merge new knowledge into an existing library file.

Rules:
- MERGE new content with existing — do not just append.
- Deduplicate overlapping information.
- Keep entries concise and structured (markdown headers, bullet points).
- Add a "Last Updated: YYYY-MM-DD" line at the end.
- If no existing content, create a well-structured new file.

Respond with ONLY the complete updated file content (no explanation)."""


class WriteAgent:
    def __init__(self, provider: LLMProvider, library_path: Path):
        self._provider = provider
        self._library_path = library_path

    def update(self, topic: str, content: str, tracker: TokenTracker | None = None) -> str:
        """Merge new content into library. Returns confirmation message."""
        self._library_path.mkdir(parents=True, exist_ok=True)

        target = self._topic_to_path(topic)
        existing = target.read_text() if target.exists() else ""

        merged = self._merge(topic, content, existing, tracker=tracker)
        target.write_text(merged)
        self._update_index(topic, target)
        return f"Updated library: {target.relative_to(self._library_path)}"

    def _topic_to_path(self, topic: str) -> Path:
        """Map topic to a file path."""
        safe_name = topic.replace(" ", "_").lower()
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        return self._library_path / safe_name

    def _merge(self, topic: str, content: str, existing: str, tracker: TokenTracker | None = None) -> str:
        """Make one LLM call to merge content."""
        user_content = (
            f"Topic: {topic}\nToday's date: {date.today().isoformat()}\n\n"
            f"Existing content:\n{existing or '(empty — new file)'}\n\n"
            f"New content to merge:\n{content}"
        )
        messages = [Message(role="user", content=user_content)]
        response = self._provider.complete(messages, system=WRITE_SYSTEM_PROMPT)
        if tracker:
            tracker.record(response.usage.input_tokens, response.usage.output_tokens)
        return response.content

    def _update_index(self, topic: str, target: Path) -> None:
        """Ensure the file is listed in index.md."""
        index_path = self._library_path / "index.md"
        relative = str(target.relative_to(self._library_path))

        if index_path.exists():
            index_content = index_path.read_text()
            if relative in index_content:
                return
            index_content = index_content.rstrip() + f"\n- {relative}\n"
        else:
            index_content = f"# Library Index\n\n- {relative}\n"

        index_path.write_text(index_content)
