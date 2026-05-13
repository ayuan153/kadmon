from __future__ import annotations

from kadmon.providers.base import LLMProvider
from kadmon.tools.base import Tool, ToolResult
from kadmon.workers import WorkerPool


class ParallelDispatchTool(Tool):
    name = "parallel_dispatch"
    description = (
        "Run independent subtasks in parallel. Each task gets its own context window and tool access. "
        "Use for tasks that don't depend on each other (e.g., reading multiple modules, updating independent files). "
        "Do NOT use for tasks where one depends on another's output."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of independent task descriptions to run in parallel",
            },
        },
        "required": ["tasks"],
    }

    def __init__(self, provider: LLMProvider, repo_root: str):
        self._pool = WorkerPool(provider, repo_root)

    def execute(self, tasks: list[str] | None = None, **kwargs) -> ToolResult:
        if not tasks:
            return ToolResult(output="Error: provide at least one task", error=True)
        if len(tasks) > 5:
            return ToolResult(output="Error: max 5 parallel tasks", error=True)

        results = self._pool.dispatch(tasks)

        parts: list[str] = []
        for r in results:
            status = "\u2713" if r.success else "\u2717"
            parts.append(f"{status} Task: {r.task}\nResult: {r.output}")

        return ToolResult(output="\n\n".join(parts))
