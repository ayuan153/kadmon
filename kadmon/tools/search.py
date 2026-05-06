import shutil
import subprocess
from pathlib import Path

from kadmon.tools.base import Tool, ToolResult


class GrepSearchTool(Tool):
    name = 'grep_search'
    description = 'Search file contents using regex. Returns matching lines with file paths and line numbers.'
    parameters = {
        'type': 'object',
        'properties': {
            'pattern': {'type': 'string', 'description': 'Regex pattern to search for'},
            'path': {'type': 'string', 'description': 'Directory to search in (relative to repo root, default: ".")'},
            'include': {'type': 'string', 'description': 'File glob filter (e.g. "*.py")'},
        },
        'required': ['pattern'],
    }

    def __init__(self, repo_root: str):
        self._root = Path(repo_root).resolve()

    def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs['pattern']
        path = kwargs.get('path', '.')
        include = kwargs.get('include')

        try:
            search_dir = (self._root / path).resolve()
            if not str(search_dir).startswith(str(self._root)):
                return ToolResult(output=f'Path escapes repository root: {path}', error=True)
        except Exception as e:
            return ToolResult(output=str(e), error=True)

        if not search_dir.is_dir():
            return ToolResult(output=f'Not a directory: {path}', error=True)

        # Try ripgrep first, fall back to grep
        if shutil.which('rg'):
            cmd = ['rg', '--no-heading', '--line-number', '--max-count', '50', pattern]
            if include:
                cmd.extend(['--glob', include])
            cmd.append(str(search_dir))
        else:
            cmd = ['grep', '-rn', pattern, str(search_dir)]
            if include:
                cmd.extend(['--include', include])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return ToolResult(output='Search timed out', error=True)

        output = result.stdout.strip()
        if not output:
            return ToolResult(output=f'No matches found for pattern: {pattern}')

        # Make paths relative to repo root
        lines = output.splitlines()[:50]
        relative_lines = []
        root_str = str(self._root) + '/'
        for line in lines:
            relative_lines.append(line.replace(root_str, ''))
        return ToolResult(output='\n'.join(relative_lines))
