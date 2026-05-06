"""Persistent symbol database using stdlib sqlite3."""

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    kind TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    start_col INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    end_col INTEGER NOT NULL,
    parent_name TEXT,
    signature TEXT,
    FOREIGN KEY (file_path) REFERENCES files(path)
);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
"""

_SYMBOL_KEYS = (
    "name", "type", "kind", "file_path", "start_line", "start_col",
    "end_line", "end_col", "parent_name", "signature",
)


class SymbolDB:
    def __init__(self, db_path: str = ".kadmon/symbols.db"):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)

    def get_file_info(self, path: str) -> tuple[float, int] | None:
        row = self._conn.execute(
            "SELECT mtime, size FROM files WHERE path = ?", (path,)
        ).fetchone()
        return (row[0], row[1]) if row else None

    def upsert_file(self, path: str, mtime: float, size: int) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO files (path, mtime, size) VALUES (?, ?, ?)",
                (path, mtime, size),
            )

    def delete_file(self, path: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM symbols WHERE file_path = ?", (path,))
            self._conn.execute("DELETE FROM files WHERE path = ?", (path,))

    def insert_symbols(self, file_path: str, symbols: list[dict]) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
            self._conn.executemany(
                """INSERT INTO symbols
                   (file_path, name, type, kind, start_line, start_col, end_line, end_col, parent_name, signature)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        file_path, s["name"], s["type"], s["kind"],
                        s["start_line"], s["start_col"], s["end_line"], s["end_col"],
                        s.get("parent_name"), s.get("signature"),
                    )
                    for s in symbols
                ],
            )

    def find_by_name(self, name: str, type: str | None = None) -> list[dict]:
        if type:
            rows = self._conn.execute(
                "SELECT name, type, kind, file_path, start_line, start_col, end_line, end_col, parent_name, signature "
                "FROM symbols WHERE name = ? AND type = ?", (name, type),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT name, type, kind, file_path, start_line, start_col, end_line, end_col, parent_name, signature "
                "FROM symbols WHERE name = ?", (name,),
            ).fetchall()
        return [dict(zip(_SYMBOL_KEYS, row)) for row in rows]

    def find_by_file(self, file_path: str, type: str | None = None) -> list[dict]:
        if type:
            rows = self._conn.execute(
                "SELECT name, type, kind, file_path, start_line, start_col, end_line, end_col, parent_name, signature "
                "FROM symbols WHERE file_path = ? AND type = ?", (file_path, type),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT name, type, kind, file_path, start_line, start_col, end_line, end_col, parent_name, signature "
                "FROM symbols WHERE file_path = ?", (file_path,),
            ).fetchall()
        return [dict(zip(_SYMBOL_KEYS, row)) for row in rows]

    def find_definitions(self, name: str) -> list[dict]:
        return self.find_by_name(name, type="definition")

    def find_references(self, name: str) -> list[dict]:
        return self.find_by_name(name, type="reference")

    def all_files(self) -> list[str]:
        rows = self._conn.execute("SELECT path FROM files").fetchall()
        return [r[0] for r in rows]

    def stats(self) -> dict:
        files = self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        symbols = self._conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        defs = self._conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE type = 'definition'"
        ).fetchone()[0]
        refs = self._conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE type = 'reference'"
        ).fetchone()[0]
        return {"files": files, "symbols": symbols, "definitions": defs, "references": refs}

    def close(self) -> None:
        self._conn.close()
