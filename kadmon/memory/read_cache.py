import hashlib


class ReadCache:
    """Tracks file content hashes to detect re-reads of unchanged files."""

    def __init__(self):
        self._hashes: dict[str, str] = {}

    def check(self, path: str, content: bytes) -> bool:
        """Returns True if content is unchanged since last read."""
        h = hashlib.sha256(content).hexdigest()[:16]
        if self._hashes.get(path) == h:
            return True
        self._hashes[path] = h
        return False

    def invalidate(self, path: str):
        """Call when a file is written/edited."""
        self._hashes.pop(path, None)

    def clear(self):
        self._hashes.clear()
