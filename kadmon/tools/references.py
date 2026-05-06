"""Tools for finding symbol definitions and references in the codebase."""

import linecache
from pathlib import Path

from kadmon.index.db import SymbolDB
from kadmon.tools.base import Tool, ToolResult

MAX_RESULTS = 50


def _read_line(file_path: str, line_no: int) -> str:
    """Read a single source line, returning empty string if unavailable."""
    line = linecache.getline(file_path, line_no)
    if not line and Path(file_path).exists():
        try:
            with open(file_path) as f:
                for i, src_line in enumerate(f, 1):
                    if i == line_no:
                        return src_line.rstrip()
        except (OSError, UnicodeDecodeError):
            return ""
    return line.rstrip()


def _format_entries(entries: list[dict], max_entries: int) -> tuple[list[str], int]:
    """Format entries as '  file:line  context' lines. Returns (lines, overflow_count)."""
    overflow = max(0, len(entries) - max_entries)
    lines = []
    for entry in entries[:max_entries]:
        context = _read_line(entry["file_path"], entry["start_line"])
        lines.append(f"  {entry['file_path']}:{entry['start_line']}  {context}")
    return lines, overflow


class FindReferencesTool(Tool):
    name = "find_references"
    description = "Find all definitions and usages of a symbol across the codebase. Requires the symbol index to be built."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Symbol name to search for"},
            "type": {
                "type": "string",
                "enum": ["definition", "reference"],
                "description": "Filter to only definitions or references",
            },
        },
        "required": ["name"],
    }

    def __init__(self, db: SymbolDB):
        self._db = db

    def execute(self, **kwargs) -> ToolResult:
        name = kwargs["name"]
        type_filter = kwargs.get("type")

        try:
            results = self._db.find_by_name(name, type=type_filter)
        except Exception as e:
            return ToolResult(output=f"Database error: {e}", error=True)

        if not results:
            return ToolResult(
                output=f"No results found for '{name}'. The symbol index may need updating.",
                error=False,
            )

        defs = [r for r in results if r["type"] == "definition"]
        refs = [r for r in results if r["type"] == "reference"]

        parts = [f"Symbol: {name}"]

        if defs and type_filter != "reference":
            parts.append("\nDefinitions:")
            lines, overflow = _format_entries(defs, MAX_RESULTS)
            parts.extend(lines)
            if overflow:
                parts.append(f"  ... and {overflow} more")

        if refs and type_filter != "definition":
            remaining = MAX_RESULTS - min(len(defs), MAX_RESULTS)
            parts.append(f"\nReferences ({len(refs)}):")
            lines, overflow = _format_entries(refs, remaining)
            parts.extend(lines)
            if overflow:
                parts.append(f"  ... and {overflow} more")

        return ToolResult(output="\n".join(parts))


class FindDefinitionTool(Tool):
    name = "find_definition"
    description = "Find where a symbol is defined. Faster than find_references when you only need the definition location."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Symbol name to search for"},
        },
        "required": ["name"],
    }

    def __init__(self, db: SymbolDB):
        self._db = db

    def execute(self, **kwargs) -> ToolResult:
        name = kwargs["name"]

        try:
            defs = self._db.find_definitions(name)
        except Exception as e:
            return ToolResult(output=f"Database error: {e}", error=True)

        if not defs:
            return ToolResult(
                output=f"No definition found for '{name}'. The symbol index may need updating.",
                error=False,
            )

        parts = [f"Symbol: {name}\n"]
        lines, overflow = _format_entries(defs, MAX_RESULTS)
        parts.extend(lines)
        if overflow:
            parts.append(f"  ... and {overflow} more")

        return ToolResult(output="\n".join(parts))
