import subprocess
from pathlib import Path

from kadmon.tools.base import Tool, ToolResult


class SubmitTool(Tool):
    name = 'submit'
    description = 'Generate a git diff of all changes as the final patch.'
    parameters = {
        'type': 'object',
        'properties': {},
        'required': [],
    }

    def __init__(self, repo_root: str):
        self._root = Path(repo_root).resolve()

    def execute(self, **kwargs) -> ToolResult:
        result = subprocess.run(
            ['git', 'diff'],
            capture_output=True,
            text=True,
            cwd=str(self._root),
        )
        diff = result.stdout.strip()
        if not diff:
            return ToolResult(
                output='No changes detected. Have you made any edits yet?',
                error=True,
            )
        return ToolResult(output=diff)
