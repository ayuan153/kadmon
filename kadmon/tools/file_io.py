from pathlib import Path

from kadmon.tools.base import Tool, ToolResult


def _resolve_path(repo_root: Path, path: str) -> Path:
    """Resolve path relative to repo_root, ensuring it doesn't escape."""
    resolved = (repo_root / path).resolve()
    if not str(resolved).startswith(str(repo_root.resolve())):
        raise ValueError(f'Path escapes repository root: {path}')
    return resolved


class ReadFileTool(Tool):
    name = 'read_file'
    description = 'Read file contents with line numbers. Supports optional line range.'
    parameters = {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'File path relative to repo root'},
            'start_line': {'type': 'integer', 'description': 'Starting line (1-indexed, inclusive)'},
            'end_line': {'type': 'integer', 'description': 'Ending line (1-indexed, inclusive)'},
        },
        'required': ['path'],
    }

    def __init__(self, repo_root: str):
        self._root = Path(repo_root).resolve()

    def execute(self, **kwargs) -> ToolResult:
        path = kwargs['path']
        try:
            resolved = _resolve_path(self._root, path)
        except ValueError as e:
            return ToolResult(output=str(e), error=True)

        if not resolved.is_file():
            # Suggest similar files in the same directory
            parent = resolved.parent
            suggestions = ''
            if parent.is_dir():
                files = [f.name for f in parent.iterdir() if f.is_file()]
                if files:
                    suggestions = f'\nFiles in {parent.relative_to(self._root)}/: {", ".join(sorted(files)[:10])}'
            return ToolResult(output=f'File not found: {path}{suggestions}', error=True)

        content = resolved.read_text()
        lines = content.splitlines()

        start = kwargs.get('start_line', 1)
        end = kwargs.get('end_line', len(lines))
        start = max(1, start)
        end = min(len(lines), end)

        numbered = [f'{i:4d} | {lines[i-1]}' for i in range(start, end + 1)]
        return ToolResult(output='\n'.join(numbered))


class WriteFileTool(Tool):
    name = 'write_file'
    description = 'Write content to a file. Creates parent directories if needed.'
    parameters = {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'File path relative to repo root'},
            'content': {'type': 'string', 'description': 'Full file content to write'},
        },
        'required': ['path', 'content'],
    }

    def __init__(self, repo_root: str):
        self._root = Path(repo_root).resolve()

    def execute(self, **kwargs) -> ToolResult:
        path = kwargs['path']
        content = kwargs['content']
        try:
            resolved = _resolve_path(self._root, path)
        except ValueError as e:
            return ToolResult(output=str(e), error=True)

        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content)
        return ToolResult(output=f'Wrote {len(content)} bytes to {path}')


class EditFileTool(Tool):
    name = 'edit_file'
    description = 'Search and replace in a file. old_str must match exactly once.'
    parameters = {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'File path relative to repo root'},
            'old_str': {'type': 'string', 'description': 'Exact string to find (must appear once)'},
            'new_str': {'type': 'string', 'description': 'Replacement string'},
        },
        'required': ['path', 'old_str', 'new_str'],
    }

    def __init__(self, repo_root: str):
        self._root = Path(repo_root).resolve()

    def execute(self, **kwargs) -> ToolResult:
        path = kwargs['path']
        old_str = kwargs['old_str']
        new_str = kwargs['new_str']

        try:
            resolved = _resolve_path(self._root, path)
        except ValueError as e:
            return ToolResult(output=str(e), error=True)

        if not resolved.is_file():
            return ToolResult(output=f'File not found: {path}', error=True)

        content = resolved.read_text()
        count = content.count(old_str)

        if count == 0:
            return ToolResult(output=f'old_str not found in {path}. Make sure it matches exactly.', error=True)
        if count > 1:
            # Find line numbers of matches
            lines = content.splitlines()
            match_lines = [i + 1 for i, line in enumerate(lines) if old_str in line]
            return ToolResult(
                output=f'old_str found {count} times in {path} (lines: {match_lines}). Must match exactly once.',
                error=True,
            )

        new_content = content.replace(old_str, new_str, 1)
        resolved.write_text(new_content)
        return ToolResult(output=f'Applied edit to {path}')


class ListDirTool(Tool):
    name = 'list_dir'
    description = 'List directory contents. Respects .gitignore patterns.'
    parameters = {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'Directory path relative to repo root (default: ".")'},
            'recursive': {'type': 'boolean', 'description': 'List recursively (default: false)'},
        },
        'required': [],
    }

    def __init__(self, repo_root: str):
        self._root = Path(repo_root).resolve()

    def _load_gitignore_patterns(self) -> list[str]:
        gitignore = self._root / '.gitignore'
        if not gitignore.is_file():
            return []
        patterns = []
        for line in gitignore.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
        return patterns

    def _is_ignored(self, path: Path, patterns: list[str]) -> bool:
        rel = str(path.relative_to(self._root))
        name = path.name
        for pattern in patterns:
            # Simple matching: check if name or relative path matches
            clean = pattern.rstrip('/')
            if name == clean or rel.startswith(clean):
                return True
        return False

    def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get('path', '.')
        recursive = kwargs.get('recursive', False)

        try:
            resolved = _resolve_path(self._root, path)
        except ValueError as e:
            return ToolResult(output=str(e), error=True)

        if not resolved.is_dir():
            return ToolResult(output=f'Not a directory: {path}', error=True)

        patterns = self._load_gitignore_patterns()
        entries = []

        if recursive:
            for item in sorted(resolved.rglob('*')):
                if self._is_ignored(item, patterns):
                    continue
                rel = item.relative_to(self._root)
                suffix = '/' if item.is_dir() else ''
                entries.append(f'{rel}{suffix}')
        else:
            for item in sorted(resolved.iterdir()):
                if self._is_ignored(item, patterns):
                    continue
                rel = item.relative_to(self._root)
                suffix = '/' if item.is_dir() else ''
                entries.append(f'{rel}{suffix}')

        return ToolResult(output='\n'.join(entries) if entries else '(empty directory)')
