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

    def find_relevant(self, query: str, tracker: TokenTracker | None = None, active_files: list[str] | None = None) -> IndexResult:
        """Returns list of relevant file paths + orthogonality signal."""
        index_path = self._library_path / "index.md"
        if not index_path.exists():
            return IndexResult()

        index_content = index_path.read_text()
        headers = self._read_file_headers(index_content, active_files)

        user_content = f"Task: {query}\n\nLibrary index:\n{index_content}\n\nFile headers:\n{headers}"
        messages = [Message(role="user", content=user_content)]
        response = self._provider.complete(messages, system=INDEX_SYSTEM_PROMPT)
        if tracker:
            tracker.record(response.usage.input_tokens, response.usage.output_tokens)
        return self._parse_response(response.content)

    def _matches_scope(self, scope_line: str, active_files: list[str]) -> bool:
        """Check if any active file matches any glob pattern in the scope line."""
        import fnmatch
        patterns = [p.strip() for p in scope_line.split(",")]
        for pattern in patterns:
            for f in active_files:
                if fnmatch.fnmatch(f, pattern):
                    return True
        return False

    def _read_file_headers(self, index_content: str, active_files: list[str] | None = None) -> str:
        """Read first ~10 lines of each file, filtering by scope."""
        headers: list[str] = []
        for line in index_content.splitlines():
            line = line.strip().lstrip("- ")
            if line.endswith(".md"):
                file_path = self._library_path / line
                if file_path.exists():
                    file_lines = file_path.read_text().splitlines()[:10]
                    # Check scope
                    scope_line = ""
                    for fl in file_lines:
                        if fl.startswith("Scope:"):
                            scope_line = fl[len("Scope:"):].strip()
                            break
                    if scope_line and active_files is not None:
                        if not self._matches_scope(scope_line, active_files):
                            continue
                    headers.append(f"--- {line} ---\n" + "\n".join(file_lines))
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
