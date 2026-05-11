import json
import time
from collections.abc import Iterator

import anthropic

from kadmon.providers.base import (
    LLMResponse,
    Message,
    StreamChunk,
    StreamEvent,
    TokenUsage,
    ToolCall,
)

_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)
_MAX_RETRIES = 3


class AnthropicProvider:
    def __init__(self, model: str, api_key: str, max_tokens: int = 8192) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=api_key)

    def complete(
        self, messages: list[Message], tools: list[dict] | None = None, system: str = ""
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [self._convert_message(m) for m in messages],
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = self._call_with_retry(kwargs)
        return self._parse_response(response)

    def stream(
        self, messages: list[Message], tools: list[dict] | None = None, system: str = ""
    ) -> Iterator[StreamChunk]:
        """Stream response chunks as they arrive."""
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [self._convert_message(m) for m in messages],
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        current_tool_json = ""
        current_tool_name = ""
        current_tool_id = ""
        input_tokens = 0
        output_tokens = 0

        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                if event.type == "message_start":
                    if hasattr(event, "message") and event.message.usage:
                        input_tokens = event.message.usage.input_tokens
                elif event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool_name = block.name
                        current_tool_id = block.id
                        current_tool_json = ""
                        yield StreamChunk(
                            event=StreamEvent.TOOL_START, tool_name=block.name, tool_id=block.id
                        )
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        content_parts.append(delta.text)
                        yield StreamChunk(event=StreamEvent.TEXT_DELTA, text=delta.text)
                    elif delta.type == "input_json_delta":
                        current_tool_json += delta.partial_json
                        yield StreamChunk(
                            event=StreamEvent.TOOL_DELTA,
                            text=delta.partial_json,
                            tool_name=current_tool_name,
                        )
                elif event.type == "content_block_stop":
                    if current_tool_name:
                        try:
                            args = json.loads(current_tool_json) if current_tool_json else {}
                        except json.JSONDecodeError:
                            args = {}
                        tool_calls.append(
                            ToolCall(id=current_tool_id, name=current_tool_name, arguments=args)
                        )
                        yield StreamChunk(
                            event=StreamEvent.TOOL_END,
                            tool_name=current_tool_name,
                            tool_id=current_tool_id,
                        )
                        current_tool_name = ""
                        current_tool_id = ""
                elif event.type == "message_delta":
                    if hasattr(event, "usage") and event.usage:
                        output_tokens = event.usage.output_tokens

        response = LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            stop_reason=stream.get_final_message().stop_reason or "",
        )
        yield StreamChunk(event=StreamEvent.DONE, response=response)

    def _convert_message(self, msg: Message) -> dict:
        if isinstance(msg.content, list):
            # Tool result blocks - pass through as-is
            return {"role": msg.role, "content": msg.content}
        return {"role": msg.role, "content": msg.content}

    def _call_with_retry(self, kwargs: dict) -> anthropic.types.Message:
        for attempt in range(_MAX_RETRIES):
            try:
                return self.client.messages.create(**kwargs)
            except _RETRYABLE:
                if attempt == _MAX_RETRIES - 1:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("Unreachable")

    def _parse_response(self, response: anthropic.types.Message) -> LLMResponse:
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))

        return LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
            stop_reason=response.stop_reason or "",
        )
