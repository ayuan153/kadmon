from dataclasses import dataclass, field
from enum import Enum
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
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    stop_reason: str = ""


@dataclass
class Message:
    role: str  # 'user', 'assistant', 'system'
    content: str | list  # str for text, list for tool results


class StreamEvent(str, Enum):
    TEXT_DELTA = "text_delta"
    TOOL_START = "tool_start"
    TOOL_DELTA = "tool_delta"
    TOOL_END = "tool_end"
    DONE = "done"


@dataclass
class StreamChunk:
    event: StreamEvent
    text: str = ""
    tool_name: str = ""
    tool_id: str = ""
    # Final response (only on DONE event)
    response: LLMResponse | None = None


class LLMProvider(Protocol):
    def complete(
        self, messages: list[Message], tools: list[dict] | None = None, system: str = ""
    ) -> LLMResponse: ...
