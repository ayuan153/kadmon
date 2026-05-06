"""Incremental index updater — walks source files and updates the symbol DB."""

from collections.abc import Callable
from pathlib import Path

from kadmon.index.db import SymbolDB

_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".java"}
_SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv"}


class IndexUpdater:
    def __init__(self, db: SymbolDB, repo_root: str):
        self._db = db
        self._root = Path(repo_root)

    def update(self, parser_func: Callable[[str], list[dict]]) -> dict:
        stats = {"added": 0, "updated": 0, "deleted": 0, "skipped": 0}
        disk_files: set[str] = set()

        for path in self._walk():
            rel = str(path.relative_to(self._root))
            disk_files.add(rel)
            st = path.stat()
            mtime, size = st.st_mtime, st.st_size

            info = self._db.get_file_info(rel)
            if info and info[0] == mtime and info[1] == size:
                stats["skipped"] += 1
                continue

            symbols = parser_func(str(path))
            self._db.upsert_file(rel, mtime, size)
            self._db.insert_symbols(rel, symbols)

            if info:
                stats["updated"] += 1
            else:
                stats["added"] += 1

        # Remove files deleted from disk
        for db_path in self._db.all_files():
            if db_path not in disk_files:
                self._db.delete_file(db_path)
                stats["deleted"] += 1

        return stats

    def _walk(self) -> list[Path]:
        results: list[Path] = []
        for ext in _EXTENSIONS:
            for path in self._root.rglob(f"*{ext}"):
                if self._should_skip(path):
                    continue
                results.append(path)
        return results

    def _should_skip(self, path: Path) -> bool:
        parts = path.relative_to(self._root).parts
        for part in parts:
            if part.startswith(".") or part in _SKIP_DIRS:
                return True
        return False
