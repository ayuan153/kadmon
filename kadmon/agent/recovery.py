import json


class LoopDetector:
    """Detects when the agent is stuck in a repetitive loop."""

    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self._recent_actions: list[str] = []
        self._recent_errors: list[str] = []

    def record_action(self, tool_name: str, args: dict) -> bool:
        """Record a tool call. Returns True if loop detected."""
        sig = f"{tool_name}:{_stable_hash(args)}"
        self._recent_actions.append(sig)
        self._recent_actions = self._recent_actions[-(self.threshold * 2):]
        if len(self._recent_actions) >= self.threshold:
            last_n = self._recent_actions[-self.threshold:]
            if len(set(last_n)) == 1:
                return True
        return False

    def record_error(self, error_msg: str) -> bool:
        """Record an error. Returns True if same error repeated threshold times."""
        normalized = error_msg[:200].strip()
        self._recent_errors.append(normalized)
        self._recent_errors = self._recent_errors[-(self.threshold * 2):]
        if len(self._recent_errors) >= self.threshold:
            last_n = self._recent_errors[-self.threshold:]
            if len(set(last_n)) == 1:
                return True
        return False

    def get_recovery_message(self) -> str:
        """Return a message to inject when a loop is detected."""
        return (
            "STOP: You are repeating the same action or hitting the same error. "
            "This approach is not working. Try a different strategy:\n"
            "1. Re-read the relevant file to check current state\n"
            "2. Try a completely different approach to solve the problem\n"
            "3. If an edit keeps failing, read the file first to get exact content\n"
            "4. If tests keep failing with the same error, analyze the error more carefully"
        )

    def reset(self):
        self._recent_actions.clear()
        self._recent_errors.clear()


def _stable_hash(d: dict) -> str:
    """Create a stable string representation of a dict for comparison."""
    return json.dumps(d, sort_keys=True, default=str)[:200]
