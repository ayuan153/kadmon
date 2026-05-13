from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from kadmon.providers.base import LLMProvider


@dataclass
class WorkerResult:
    task: str
    output: str
    success: bool
    files_modified: list[str] = field(default_factory=list)


class WorkerPool:
    """Runs independent subtasks in parallel via separate AgentLoops."""

    def __init__(self, provider: LLMProvider, repo_root: str, max_workers: int = 3):
        self._provider = provider
        self._repo_root = repo_root
        self._max_workers = max_workers

    def dispatch(self, tasks: list[str]) -> list[WorkerResult]:
        """Run tasks in parallel. Returns results in same order as input."""
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {executor.submit(self._run_worker, task): i for i, task in enumerate(tasks)}
            results: list[WorkerResult | None] = [None] * len(tasks)
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = WorkerResult(task=tasks[idx], output=f"Worker error: {e}", success=False)
        return [r for r in results if r is not None]

    def _run_worker(self, task: str) -> WorkerResult:
        """Run a single worker AgentLoop."""
        from kadmon.tools import create_default_registry
        from kadmon.agent.loop import AgentLoop

        tools = create_default_registry(self._repo_root, provider=self._provider)
        agent = AgentLoop(
            provider=self._provider,
            tools=tools,
            max_iterations=15,
            use_planning=False,
            repo_root=self._repo_root,
        )
        result = agent.run(task)
        return WorkerResult(
            task=task,
            output=result if result else "Worker completed without producing a patch.",
            success=bool(result),
        )
