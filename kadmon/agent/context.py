from kadmon.providers.base import Message

# Max size for a single tool result to prevent context blowup
MAX_MESSAGE_CHARS = 50000


class ContextManager:
    """Manages conversation history within token budget."""

    def __init__(self, max_tokens: int = 200000):
        self.messages: list[Message] = []
        self.max_tokens = max_tokens
        self._token_estimate = 0

    def add(self, message: Message):
        message = self._truncate_if_needed(message)
        self.messages.append(message)
        self._token_estimate += len(str(message.content)) // 4
        self._maybe_compact()

    def _truncate_if_needed(self, message: Message) -> Message:
        """Truncate oversized tool results."""
        if isinstance(message.content, list):
            truncated = []
            for block in message.content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if len(content) > MAX_MESSAGE_CHARS:
                        block = {
                            **block,
                            "content": content[:MAX_MESSAGE_CHARS] + "\n\n[truncated]",
                        }
                truncated.append(block)
            return Message(role=message.role, content=truncated)
        if isinstance(message.content, str) and len(message.content) > MAX_MESSAGE_CHARS:
            return Message(
                role=message.role,
                content=message.content[:MAX_MESSAGE_CHARS] + "\n\n[truncated]",
            )
        return message

    def _maybe_compact(self):
        while self._token_estimate > self.max_tokens * 0.9 and len(self.messages) > 4:
            removed = self.messages.pop(2)
            self._token_estimate -= len(str(removed.content)) // 4

    def to_messages(self) -> list[Message]:
        return list(self.messages)

    @property
    def utilization(self) -> float:
        return self._token_estimate / self.max_tokens if self.max_tokens > 0 else 0
