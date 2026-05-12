from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenTracker:
    """Tracks token usage across library subagent calls within a session."""

    input_tokens: int = 0
    output_tokens: int = 0
    call_count: int = 0

    def record(self, input_tokens: int, output_tokens: int) -> None:
        """Record tokens from one LLM call."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.call_count += 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def summary(self) -> str:
        """Human-readable summary."""
        return f"{self.call_count} calls, {self.total_tokens} tokens ({self.input_tokens} in, {self.output_tokens} out)"
