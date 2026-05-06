import subprocess
from pathlib import Path

from kadmon.tools.base import Tool, ToolResult

MAX_OUTPUT = 10000


class ShellTool(Tool):
    name = 'shell'
    description = 'Run a bash command. Returns stdout, stderr, and exit code.'
    parameters = {
        'type': 'object',
        'properties': {
            'command': {'type': 'string', 'description': 'Bash command to execute'},
        },
        'required': ['command'],
    }

    def __init__(self, repo_root: str):
        self._root = Path(repo_root).resolve()

    def execute(self, **kwargs) -> ToolResult:
        command = kwargs['command']
        if not command.strip():
            return ToolResult(output='Empty command', error=True)

        try:
            result = subprocess.run(
                ['bash', '-c', command],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self._root),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(output='Command timed out after 120s', error=True)

        output = result.stdout + result.stderr
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + '\n... (truncated)'

        return ToolResult(output=f'{output}\n[exit code: {result.returncode}]')
