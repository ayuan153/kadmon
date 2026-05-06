"""file_skeleton tool: shows file structure without bodies."""

import re
from pathlib import Path

from kadmon.index.parser import SymbolParser
from kadmon.tools.base import Tool, ToolResult


class FileSkeletonTool(Tool):
    name = "file_skeleton"
    description = (
        "Show file structure: function/class signatures, line counts, "
        "and call relationships. Use this to understand a file without reading its full content."
    )
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "File path relative to repo root"}},
        "required": ["path"],
    }

    def __init__(self, repo_root: str):
        self._root = Path(repo_root).resolve()
        self._parser = SymbolParser()

    def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")
        resolved = (self._root / path).resolve()
        # Validate not escaping repo root
        if not str(resolved).startswith(str(self._root)):
            return ToolResult(output="Path escapes repository root.", error=True)
        if not resolved.is_file():
            return ToolResult(
                output=f"File not found: {path}\nHint: check the path or use a search tool to locate it.",
                error=True,
            )

        rel_path = resolved.relative_to(self._root)
        total_lines = resolved.read_text(errors="replace").count("\n") + 1

        try:
            symbols = self._parser.parse_file(str(resolved))
            if not symbols:
                raise ValueError("no symbols parsed")
            output = self._format(symbols, rel_path, total_lines)
        except Exception:
            # Fallback: regex-based signatures
            output = self._fallback(resolved, rel_path, total_lines)

        return ToolResult(output=output)

    def _format(self, symbols: list[dict], rel_path: Path, total_lines: int) -> str:
        defs = [s for s in symbols if s["type"] == "definition"]
        refs = [s for s in symbols if s["type"] == "reference"]
        # Set of defined function/method names for call graph filtering
        defined_names = {s["name"] for s in defs if s["kind"] in ("function", "method")}

        # Build call graph: for each def, find refs within its line range
        def calls_for(d: dict) -> list[str]:
            start, end = d["start_line"], d["end_line"]
            called = []
            for r in refs:
                if start <= r["start_line"] <= end and r["name"] in defined_names and r["name"] != d["name"]:
                    if r["name"] not in called:
                        called.append(r["name"])
            return called

        # Group: top-level defs and classes with their methods
        classes = {s["name"]: s for s in defs if s["kind"] == "class"}
        methods_by_class: dict[str, list[dict]] = {name: [] for name in classes}
        top_level: list[dict] = []

        for s in defs:
            if s["kind"] == "class":
                continue
            if s["parent_name"] and s["parent_name"] in classes:
                methods_by_class[s["parent_name"]].append(s)
            elif s["kind"] == "function":
                top_level.append(s)

        lines_out = [f"{rel_path} ({total_lines} lines)", ""]

        # Render classes
        for cls_name, cls_sym in classes.items():
            lines_out.append(f"class {cls_name} (lines {cls_sym['start_line']}-{cls_sym['end_line']}):")
            for m in methods_by_class[cls_name]:
                line_count = m["end_line"] - m["start_line"] + 1
                sig = self._clean_sig(m["signature"])
                calls = calls_for(m)
                suffix = f" → calls: {', '.join(calls)}" if calls else ""
                lines_out.append(f"  {sig}  [{line_count} lines]{suffix}")
            lines_out.append("")

        # Render top-level functions
        for f in top_level:
            line_count = f["end_line"] - f["start_line"] + 1
            sig = self._clean_sig(f["signature"])
            calls = calls_for(f)
            suffix = f" → calls: {', '.join(calls)}" if calls else ""
            lines_out.append(f"{sig}  [{line_count} lines]{suffix}")

        return "\n".join(lines_out).rstrip()

    def _clean_sig(self, sig: str) -> str:
        """Strip trailing colon and leading whitespace/decorators."""
        sig = sig.strip()
        if sig.endswith(":"):
            sig = sig[:-1].rstrip()
        return sig

    def _fallback(self, file_path: Path, rel_path: Path, total_lines: int) -> str:
        """Regex fallback when tree-sitter parsing fails."""
        content = file_path.read_text(errors="replace")
        sigs = re.findall(r"^[ \t]*((?:def|class|function|async function)\s+\w+[^\n]*)", content, re.MULTILINE)
        lines_out = [f"{rel_path} ({total_lines} lines) [fallback mode]", ""]
        for sig in sigs:
            lines_out.append(sig.rstrip(":").rstrip())
        return "\n".join(lines_out).rstrip() if sigs else f"{rel_path} ({total_lines} lines)\n\nNo symbols found."
