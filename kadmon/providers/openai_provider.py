"""OpenAI provider for kadmon."""

import json
import time

import openai

from kadmon.providers.base import LLMResponse, Message, TokenUsage, ToolCall

_MAX_RETRIES = 3


class OpenAIProvider:
    """LLM provider using OpenAI API (GPT-4o, o1, etc.)."""

    def __init__(self, model: str = "gpt-4o", api_key: str = "", max_tokens: int = 8192) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.client = openai.OpenAI(api_key=api_key)

    def complete(
        self, messages: list[Message], tools: list[dict] | None = None, system: str = ""
    ) -> LLMResponse:
        oai_messages: list[dict] = []
        if system:
            oai_messages.append({"role": "system", "content": system})

        for msg in messages:
            converted = self._convert_message(msg)
            if isinstance(converted, dict) and "_multi" in converted:
                oai_messages.extend(converted["_multi"])
            else:
                oai_messages.append(converted)

        kwargs: dict = {
            "model": self.model,
            "messages": oai_messages,
            "max_completion_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = [self._convert_tool(t) for t in tools]

        response = self._call_with_retry(kwargs)
        return self._parse_response(response)

    def _convert_message(self, msg: Message) -> dict:
        if isinstance(msg.content, list):
            if msg.role == "assistant":
                content = ""
                tool_calls = []
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            content = block.get("text", "")
                        elif block.get("type") == "tool_use":
                            tool_calls.append(
                                {
                                    "id": block["id"],
                                    "type": "function",
                                    "function": {
                                        "name": block["name"],
                                        "arguments": json.dumps(block.get("input", {})),
                                    },
                                }
                            )
                result: dict = {"role": "assistant", "content": content or None}
                if tool_calls:
                    result["tool_calls"] = tool_calls
                return result
            else:
                # Tool results — OpenAI expects each as a separate role='tool' message
                results = []
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        results.append(
                            {
                                "role": "tool",
                                "tool_call_id": block["tool_use_id"],
                                "content": block.get("content", ""),
                            }
                        )
                if len(results) == 1:
                    return results[0]
                return {"_multi": results}
        return {"role": msg.role, "content": msg.content}

    def _convert_tool(self, tool: dict) -> dict:
        """Convert internal tool format to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        }

    def _call_with_retry(self, kwargs: dict):
        for attempt in range(_MAX_RETRIES):
            try:
                return self.client.chat.completions.create(**kwargs)
            except (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError):
                if attempt == _MAX_RETRIES - 1:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("Unreachable")

    def _parse_response(self, response) -> LLMResponse:
        choice = response.choices[0]
        msg = choice.message

        content = msg.content or ""
        tool_calls = []

        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
            ),
            stop_reason=choice.finish_reason or "",
        )
