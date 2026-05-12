from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kadmon.memory.token_tracker import TokenTracker
from kadmon.providers.base import LLMProvider, Message


INDEX_SYSTEM_PROMPT = """You are the Library Index agent. Given a task description and a library index, determine which files are relevant.

Respond in this exact format:
FILES: path1.md, path2.md
ORTHOGONAL: true/false

Rules:
- Return only files that will actually help with the task.
- ORTHOGONAL=true if sessions/current.md describes work UNRELATED to the current task.
- If nothing is relevant, respond: FILES: none"""


@dataclass
class IndexResult:
    files: list[str] = field(default_factory=list)
    orthogonal: bool = False


class IndexAgent:
    def __init__(self, provider: LLMProvider, library_path: Path):
        self._provider = provider
        self._library_path = library_path

    def find_relevant(self, query: str, tracker: TokenTracker | None = None) -> IndexResult:
        """Returns list of relevant file paths + orthogonality signal."""
        index_path = self._library_path / "index.md"
        if not index_path.exists():
            return IndexResult()

        index_content = index_path.read_text()
        headers = self._read_file_headers(index_content)

        user_content = f"Task: {query}\n\nLibrary index:\n{index_content}\n\nFile headers:\n{headers}"
        messages = [Message(role="user", content=user_content)]
        response = self._provider.complete(messages, system=INDEX_SYSTEM_PROMPT)
        if tracker:
            tracker.record(response.usage.input_tokens, response.usage.output_tokens)
        return self._parse_response(response.content)

    def _read_file_headers(self, index_content: str) -> str:
        """Read first ~10 lines of each file referenced in the index."""
        headers: list[str] = []
        for line in index_content.splitlines():
            line = line.strip().lstrip("- ")
            if line.endswith(".md"):
                file_path = self._library_path / line
                if file_path.exists():
                    lines = file_path.read_text().splitlines()[:10]
                    headers.append(f"--- {line} ---\n" + "\n".join(lines))
        return "\n\n".join(headers)

    def _parse_response(self, content: str) -> IndexResult:
        """Parse LLM response into IndexResult."""
        files: list[str] = []
        orthogonal = False

        for line in content.splitlines():
            line = line.strip()
            if line.upper().startswith("FILES:"):
                raw = line[len("FILES:"):].strip()
                if raw.lower() != "none":
                    files = [f.strip() for f in raw.split(",") if f.strip()]
            elif line.upper().startswith("ORTHOGONAL:"):
                orthogonal = line[len("ORTHOGONAL:"):].strip().lower() == "true"

        return IndexResult(files=files, orthogonal=orthogonal)
