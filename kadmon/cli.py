import os

import click


@click.group()
def main():
    """Kadmon - an LLM coding agent."""


@main.command()
@click.option("--task", required=True, type=str, help="Task description")
@click.option("--repo", default=".", type=click.Path(exists=True), help="Repository path")
@click.option("--model", default="claude-sonnet-4-20250514", type=str, help="Model to use")
def run(task: str, repo: str, model: str):
    """Run kadmon on a task."""
    from kadmon.providers.anthropic import AnthropicProvider
    from kadmon.tools import build_index, create_default_registry
    from kadmon.agent import AgentLoop

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        click.echo('Error: ANTHROPIC_API_KEY not set', err=True)
        raise SystemExit(1)

    repo_path = os.path.abspath(repo)
    provider = AnthropicProvider(model=model, api_key=api_key)
    db = build_index(repo_path)
    tools = create_default_registry(repo_path, db=db)
    agent = AgentLoop(provider=provider, tools=tools)
    result = agent.run(task)
    db.close()
    if result:
        click.echo(result)
    else:
        click.echo('Agent did not produce a result.', err=True)


@main.command('eval')
@click.option('--dataset', type=click.Path(exists=True), help='Path to SWE-bench instances JSON')
@click.option('--limit', type=int, default=None, help='Max instances to run')
@click.option('--output', default='eval_results', help='Output directory')
@click.option('--model', default='claude-sonnet-4-20250514')
def eval_cmd(dataset, limit, output, model):
    """Run kadmon against SWE-bench instances."""
    import json

    from kadmon.eval import SWEBenchRunner

    if not dataset:
        click.echo('Error: --dataset required (path to instances JSON)', err=True)
        raise SystemExit(1)

    with open(dataset) as f:
        instances = json.load(f)

    if limit:
        instances = instances[:limit]

    click.echo(f'Running {len(instances)} instances with {model}...')
    runner = SWEBenchRunner(model=model)
    summary = runner.run_dataset(instances, output_dir=output)
    click.echo(f'\nResults: {summary.resolved}/{summary.total} resolved ({summary.resolve_rate:.1%})')
    click.echo(f'Errors: {summary.errored}')
    click.echo(f'Output: {output}/')
