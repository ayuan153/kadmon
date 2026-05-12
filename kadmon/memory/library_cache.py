from __future__ import annotations


class LibraryCache:
    """Per-session cache for library_read results."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def get(self, query: str) -> str | None:
        return self._cache.get(query)

    def set(self, query: str, result: str) -> None:
        self._cache[query] = result

    def clear(self) -> None:
        self._cache.clear()
