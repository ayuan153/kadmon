from kadmon.providers.base import Message


class ContextManager:
    """Manages conversation history within token budget."""

    def __init__(self, max_tokens: int = 200000):
        self.messages: list[Message] = []
        self.max_tokens = max_tokens
        self._token_estimate = 0

    def add(self, message: Message):
        self.messages.append(message)
        self._token_estimate += len(str(message.content)) // 4
        self._maybe_compact()

    def _maybe_compact(self):
        # If over 90% budget, drop oldest messages (keep first 2)
        while self._token_estimate > self.max_tokens * 0.9 and len(self.messages) > 4:
            removed = self.messages.pop(2)
            self._token_estimate -= len(str(removed.content)) // 4

    def to_messages(self) -> list[Message]:
        return list(self.messages)

    @property
    def utilization(self) -> float:
        return self._token_estimate / self.max_tokens if self.max_tokens > 0 else 0
