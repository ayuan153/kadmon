import time

import anthropic

from kadmon.providers.base import LLMResponse, Message, TokenUsage, ToolCall

_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)
_MAX_RETRIES = 3


class BedrockProvider:
    """LLM provider using Anthropic Claude via AWS Bedrock."""

    def __init__(self, model: str, aws_region: str = "us-west-2", max_tokens: int = 8192) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.client = anthropic.AnthropicBedrock(aws_region=aws_region)

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

    def _convert_message(self, msg: Message) -> dict:
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
