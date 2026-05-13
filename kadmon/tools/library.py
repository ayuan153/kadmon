from __future__ import annotations

from pathlib import Path

from kadmon.memory.library_cache import LibraryCache
from kadmon.memory.token_tracker import TokenTracker
from kadmon.providers.base import LLMProvider
from kadmon.tools.base import Tool, ToolResult
from kadmon.memory.agents.index_agent import IndexAgent
from kadmon.memory.agents.prune_agent import PruneAgent
from kadmon.memory.agents.read_agent import ReadAgent
from kadmon.memory.agents.write_agent import WriteAgent


class LibraryReadTool(Tool):
    name = "library_read"
    description = "Query the project library for relevant context. Use at task start or when you need project knowledge."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "What you need to know"}},
        "required": ["query"],
    }

    def __init__(self, provider: LLMProvider, repo_root: str):
        self._library_path = Path(repo_root) / ".kadmon" / "library"
        self._index_agent = IndexAgent(provider, self._library_path)
        self._prune_agent = PruneAgent(provider, self._library_path)
        self._read_agent = ReadAgent(provider, self._library_path)
        self.tracker = TokenTracker()
        self._cache = LibraryCache()
        self.active_files: list[str] = []

    def execute(self, query: str) -> ToolResult:
        cached = self._cache.get(query)
        if cached is not None:
            return ToolResult(output=cached)

        result = self._index_agent.find_relevant(query, tracker=self.tracker, active_files=self.active_files or None)
        if result.orthogonal:
            self._prune_agent.prune(query, tracker=self.tracker)
        if not result.files:
            return ToolResult(output="No relevant library context found.")
        synthesis = self._read_agent.synthesize(result.files, query, tracker=self.tracker)
        self._cache.set(query, synthesis)
        return ToolResult(output=synthesis)


class LibraryWriteTool(Tool):
    name = "library_write"
    description = "Save learnings to the project library. Use after completing work or discovering important patterns."
    parameters = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Category: architecture, conventions, decisions, or custom"},
            "content": {"type": "string", "description": "What you learned"},
        },
        "required": ["topic", "content"],
    }

    def __init__(self, provider: LLMProvider, repo_root: str):
        self._library_path = Path(repo_root) / ".kadmon" / "library"
        self._write_agent = WriteAgent(provider, self._library_path)
        self.tracker = TokenTracker()

    def execute(self, topic: str, content: str) -> ToolResult:
        msg = self._write_agent.update(topic, content, tracker=self.tracker)
        return ToolResult(output=msg)


class LibraryStatusTool(Tool):
    name = "library_status"
    description = "Check what's in the project library. No LLM call — just reads the index."
    parameters = {"type": "object", "properties": {}, "required": []}

    def __init__(self, repo_root: str, read_tracker: TokenTracker | None = None, write_tracker: TokenTracker | None = None):
        self._library_path = Path(repo_root) / ".kadmon" / "library"
        self._read_tracker = read_tracker
        self._write_tracker = write_tracker

    def execute(self) -> ToolResult:
        index_path = self._library_path / "index.md"
        if not index_path.exists():
            return ToolResult(output=self._with_usage("Library is empty."))

        lines: list[str] = []
        for line in index_path.read_text().splitlines():
            entry = line.strip().lstrip("- ")
            if entry.endswith(".md") and entry != "index.md":
                file_path = self._library_path / entry
                size = file_path.stat().st_size if file_path.exists() else 0
                lines.append(f"  {entry} ({size} bytes)")

        if not lines:
            return ToolResult(output=self._with_usage("Library is empty."))
        return ToolResult(output=self._with_usage("Library contents:\n" + "\n".join(lines)))

    def _with_usage(self, output: str) -> str:
        """Append token usage info if trackers have data."""
        usage_parts: list[str] = []
        if self._read_tracker and self._read_tracker.call_count > 0:
            usage_parts.append(f"Read: {self._read_tracker.summary()}")
        if self._write_tracker and self._write_tracker.call_count > 0:
            usage_parts.append(f"Write: {self._write_tracker.summary()}")
        if usage_parts:
            output += "\n\nToken usage this session:\n  " + "\n  ".join(usage_parts)
        return output
