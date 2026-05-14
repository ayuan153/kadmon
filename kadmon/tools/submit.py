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

    def __init__(self, repo_root: str, verify_tool=None):
        self._root = Path(repo_root).resolve()
        self._verify_tool = verify_tool

    def execute(self, **kwargs) -> ToolResult:
        if self._verify_tool and not self._verify_tool.last_passed:
            return ToolResult(
                output="Cannot submit: no verification has passed this session. Run verify(scope='full') first.",
                error=True,
            )
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
