import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EvalResult:
    instance_id: str
    patch: str = ''
    resolved: bool = False
    error: str = ''
    tokens_used: int = 0
    duration_seconds: float = 0
    iterations: int = 0


@dataclass
class EvalSummary:
    total: int = 0
    resolved: int = 0
    errored: int = 0
    results: list[EvalResult] = field(default_factory=list)

    @property
    def resolve_rate(self) -> float:
        return self.resolved / self.total if self.total > 0 else 0


class SWEBenchRunner:
    """Runs kadmon against SWE-bench instances."""

    def __init__(self, model: str = 'claude-sonnet-4-20250514', max_workers: int = 1):
        self.model = model
        self.max_workers = max_workers

    def run_instance(self, instance: dict) -> EvalResult:
        """Run kadmon on a single SWE-bench instance."""
        instance_id = instance['instance_id']
        start = time.time()

        try:
            repo_dir = self._setup_repo(instance)

            from kadmon.agent.loop import AgentLoop
            from kadmon.providers.anthropic import AnthropicProvider
            from kadmon.tools import create_default_registry

            api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            provider = AnthropicProvider(model=self.model, api_key=api_key)
            tools = create_default_registry(str(repo_dir))
            agent = AgentLoop(provider=provider, tools=tools)

            task = self._format_task(instance)
            patch = agent.run(task)

            return EvalResult(
                instance_id=instance_id,
                patch=patch,
                resolved=bool(patch),
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return EvalResult(
                instance_id=instance_id,
                error=str(e),
                duration_seconds=time.time() - start,
            )

    def run_dataset(self, instances: list[dict], output_dir: str = 'eval_results') -> EvalSummary:
        """Run kadmon on multiple instances."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        summary = EvalSummary(total=len(instances))

        for instance in instances:
            result = self.run_instance(instance)
            summary.results.append(result)
            if result.resolved:
                summary.resolved += 1
            if result.error:
                summary.errored += 1

            # Save individual result
            result_path = Path(output_dir) / f"{result.instance_id}.json"
            result_path.write_text(json.dumps({
                'instance_id': result.instance_id,
                'patch': result.patch,
                'resolved': result.resolved,
                'error': result.error,
                'duration': result.duration_seconds,
            }, indent=2))

        # Save summary
        summary_path = Path(output_dir) / 'summary.json'
        summary_path.write_text(json.dumps({
            'total': summary.total,
            'resolved': summary.resolved,
            'errored': summary.errored,
            'resolve_rate': summary.resolve_rate,
        }, indent=2))

        return summary

    def _setup_repo(self, instance: dict) -> Path:
        """Clone repo and checkout base commit."""
        repo_dir = Path(tempfile.mkdtemp(prefix='kadmon_eval_'))
        repo_url = f"https://github.com/{instance['repo']}.git"

        subprocess.run(
            ['git', 'clone', '--quiet', repo_url, str(repo_dir)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ['git', 'checkout', '--quiet', instance['base_commit']],
            cwd=str(repo_dir), check=True, capture_output=True,
        )
        return repo_dir

    def _format_task(self, instance: dict) -> str:
        """Format the SWE-bench instance as a task for the agent."""
        parts = [f"Fix the following GitHub issue:\n\n{instance['problem_statement']}"]
        if instance.get('hints_text'):
            parts.append(f"\nHints:\n{instance['hints_text']}")
        return '\n'.join(parts)
