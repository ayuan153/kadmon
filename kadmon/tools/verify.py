from __future__ import annotations

import json

from kadmon.qa import QARunner
from kadmon.tools.base import Tool, ToolResult


class VerifyTool(Tool):
    name = "verify"
    description = (
        "Run verification to prove changes work. Choose scope based on moment: "
        "'targeted' after each edit (fast), 'module' after a plan step, "
        "'full' before submitting, 'lint' for style checks, "
        "'custom' for arbitrary commands (e.g., curl, scripts), "
        "'discover' to see what test infrastructure exists."
    )
    parameters = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["targeted", "module", "full", "lint", "custom", "discover"],
                "description": "Verification scope",
            },
            "target": {
                "type": "string",
                "description": "Test file/function path (for targeted/module scope)",
            },
            "command": {
                "type": "string",
                "description": "Custom command to run (for custom scope)",
            },
        },
        "required": ["scope"],
    }

    def __init__(self, repo_root: str):
        self._runner = QARunner(repo_root)
        self.last_passed = False

    def execute(self, scope: str = "full", target: str = "", command: str = "", **kwargs) -> ToolResult:
        if scope == "discover":
            profile = self._runner.discover()
            output = json.dumps(profile, indent=2)
            return ToolResult(output=f"Verification profile:\n{output}")
        elif scope == "targeted":
            if not target:
                return ToolResult(output="Error: 'target' required for targeted scope", error=True)
            result = self._runner.run_targeted(target)
        elif scope == "module":
            if not target:
                return ToolResult(output="Error: 'target' required for module scope", error=True)
            result = self._runner.run_module(target)
        elif scope == "full":
            result = self._runner.run_full()
        elif scope == "lint":
            result = self._runner.run_lint()
        elif scope == "custom":
            if not command:
                return ToolResult(output="Error: 'command' required for custom scope", error=True)
            result = self._runner.run_command(command)
        else:
            return ToolResult(output=f"Unknown scope: {scope}", error=True)

        if result.passed:
            self.last_passed = True

        status = "\u2713 PASSED" if result.passed else "\u2717 FAILED"
        output = f"{status} ({result.duration:.1f}s)\nCommand: {result.command}\n\n{result.output}"
        return ToolResult(output=output, error=not result.passed)
