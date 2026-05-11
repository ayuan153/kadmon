"""Google Gemini provider for kadmon."""

import time
import uuid

from kadmon.providers.base import LLMResponse, Message, TokenUsage, ToolCall

_MAX_RETRIES = 3


class GeminiProvider:
    """LLM provider using Google Gemini API."""

    def __init__(
        self, model: str = "gemini-2.5-flash", api_key: str = "", max_tokens: int = 8192
    ) -> None:
        from google import genai

        self.model = model
        self.max_tokens = max_tokens
        self.client = genai.Client(api_key=api_key)

    def complete(
        self, messages: list[Message], tools: list[dict] | None = None, system: str = ""
    ) -> LLMResponse:
        from google.genai import types

        contents = [self._convert_message(msg) for msg in messages]

        config_kwargs: dict = {"max_output_tokens": self.max_tokens}
        if system:
            config_kwargs["system_instruction"] = system
        if tools:
            config_kwargs["tools"] = [self._convert_tools(tools)]

        config = types.GenerateContentConfig(**config_kwargs)
        response = self._call_with_retry(contents, config)
        return self._parse_response(response)

    def _convert_message(self, msg: Message):
        from google.genai import types

        role = "model" if msg.role == "assistant" else "user"

        if isinstance(msg.content, list):
            parts = []
            for block in msg.content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    parts.append(types.Part.from_text(text=block["text"]))
                elif block.get("type") == "tool_use":
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                name=block["name"], args=block.get("input", {})
                            )
                        )
                    )
                elif block.get("type") == "tool_result":
                    parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=block.get("name", "tool"),
                                response={"result": block.get("content", "")},
                            )
                        )
                    )
            return types.Content(role=role, parts=parts)

        return types.Content(role=role, parts=[types.Part.from_text(text=msg.content)])

    def _convert_tools(self, tools: list[dict]):
        from google.genai import types

        declarations = [
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=tool.get("input_schema", {}),
            )
            for tool in tools
        ]
        return types.Tool(function_declarations=declarations)

    def _call_with_retry(self, contents, config):
        for attempt in range(_MAX_RETRIES):
            try:
                return self.client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
            except Exception as e:
                if attempt == _MAX_RETRIES - 1:
                    raise
                if "429" in str(e) or "500" in str(e) or "503" in str(e):
                    time.sleep(2**attempt)
                    continue
                raise
        raise RuntimeError("Unreachable")

    def _parse_response(self, response) -> LLMResponse:
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        candidate = response.candidates[0]
        for part in candidate.content.parts:
            if part.text:
                content_parts.append(part.text)
            elif part.function_call:
                fc = part.function_call
                tool_calls.append(
                    ToolCall(
                        id=uuid.uuid4().hex[:8],
                        name=fc.name,
                        arguments=dict(fc.args) if fc.args else {},
                    )
                )

        usage = response.usage_metadata
        return LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=usage.prompt_token_count if usage else 0,
                output_tokens=usage.candidates_token_count if usage else 0,
            ),
            stop_reason=candidate.finish_reason.name if candidate.finish_reason else "",
        )
