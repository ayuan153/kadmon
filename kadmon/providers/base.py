from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResponse:
    content: str = ''
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    stop_reason: str = ''


@dataclass
class Message:
    role: str  # 'user', 'assistant', 'system'
    content: str | list  # str for text, list for tool results


class LLMProvider(Protocol):
    def complete(self, messages: list[Message], tools: list[dict] | None = None, system: str = '') -> LLMResponse: ...
