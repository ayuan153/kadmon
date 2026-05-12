from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kadmon.memory.token_tracker import TokenTracker
from kadmon.providers.base import LLMProvider, Message


PRUNE_SYSTEM_PROMPT = """You are the Library Prune agent. Your job is to keep the library lean and relevant.

Given the current library index and file contents, decide what to prune.

Respond in this exact format:
ARCHIVE: filename_for_archive.md
REMOVE: file1.md, file2.md
KEEP: file1.md, file2.md

Rules:
- ARCHIVE: suggest a descriptive filename for archiving sessions/current.md
- REMOVE: list files that are clearly stale or redundant (empty list if none)
- KEEP: list all other files
- Be conservative — when in doubt, keep the entry."""


@dataclass
class PruneResult:
    archived: str = ""
    removed: list[str] = field(default_factory=list)


class PruneAgent:
    def __init__(self, provider: LLMProvider, library_path: Path):
        self._provider = provider
        self._library_path = library_path

    def prune(self, current_task: str, tracker: TokenTracker | None = None) -> PruneResult:
        """Archive current session and prune stale entries."""
        current_path = self._library_path / "sessions" / "current.md"
        if not current_path.exists():
            return PruneResult()

        index_path = self._library_path / "index.md"
        index_content = index_path.read_text() if index_path.exists() else ""
        session_content = current_path.read_text()

        archive_name, removed = self._decide(current_task, index_content, session_content, tracker=tracker)
        self._archive_session(current_path, archive_name)
        self._remove_files(removed)
        self._update_index(removed)
        return PruneResult(archived=archive_name, removed=removed)

    def _decide(self, task: str, index_content: str, session_content: str, tracker: TokenTracker | None = None) -> tuple[str, list[str]]:
        """One LLM call to decide archive name and removals."""
        user_content = (
            f"Current task: {task}\n\n"
            f"Library index:\n{index_content}\n\n"
            f"sessions/current.md:\n{session_content}"
        )
        messages = [Message(role="user", content=user_content)]
        response = self._provider.complete(messages, system=PRUNE_SYSTEM_PROMPT)
        if tracker:
            tracker.record(response.usage.input_tokens, response.usage.output_tokens)
        return self._parse_response(response.content)

    def _parse_response(self, content: str) -> tuple[str, list[str]]:
        """Parse LLM response into archive name and removal list."""
        archive_name = "session.md"
        removed: list[str] = []

        for line in content.splitlines():
            line = line.strip()
            if line.upper().startswith("ARCHIVE:"):
                name = line[len("ARCHIVE:"):].strip()
                if name:
                    archive_name = name if name.endswith(".md") else f"{name}.md"
            elif line.upper().startswith("REMOVE:"):
                raw = line[len("REMOVE:"):].strip()
                if raw and raw.lower() != "none":
                    removed = [f.strip() for f in raw.split(",") if f.strip()]

        return archive_name, removed

    def _archive_session(self, current_path: Path, archive_name: str) -> None:
        """Move sessions/current.md to sessions/archive/{archive_name}."""
        archive_dir = current_path.parent / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        dest = archive_dir / archive_name
        current_path.rename(dest)

    def _remove_files(self, removed: list[str]) -> None:
        """Remove files marked for deletion."""
        for filename in removed:
            path = self._library_path / filename
            if path.exists():
                path.unlink()

    def _update_index(self, removed: list[str]) -> None:
        """Remove pruned entries from index.md."""
        index_path = self._library_path / "index.md"
        if not index_path.exists() or not removed:
            return
        lines = index_path.read_text().splitlines()
        kept = [line for line in lines if not any(r in line for r in removed)]
        index_path.write_text("\n".join(kept) + "\n")
