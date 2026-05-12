from __future__ import annotations

from pathlib import Path

from kadmon.memory.token_tracker import TokenTracker
from kadmon.providers.base import LLMProvider, Message


READ_SYSTEM_PROMPT = """You are the Library Read agent. Synthesize the provided library files into concise, actionable context.

Rules:
- Synthesize into a focused summary (max ~500 words).
- Include specific details (file paths, function names, decisions).
- End with "For more detail, see: [file paths]" if useful.
- Do NOT return raw file contents."""


class ReadAgent:
    def __init__(self, provider: LLMProvider, library_path: Path):
        self._provider = provider
        self._library_path = library_path

    def synthesize(self, files: list[str], query: str, tracker: TokenTracker | None = None) -> str:
        """Read files and return synthesized context."""
        file_contents = self._read_files(files)
        if not file_contents:
            return "No relevant library context found."

        user_content = f"Task: {query}\n\nLibrary files:\n{file_contents}"
        messages = [Message(role="user", content=user_content)]
        response = self._provider.complete(messages, system=READ_SYSTEM_PROMPT)
        if tracker:
            tracker.record(response.usage.input_tokens, response.usage.output_tokens)
        return response.content

    def _read_files(self, files: list[str]) -> str:
        """Read and concatenate file contents."""
        parts: list[str] = []
        for filename in files:
            file_path = self._library_path / filename
            if file_path.exists():
                content = file_path.read_text()
                parts.append(f"--- {filename} ---\n{content}")
        return "\n\n".join(parts)
