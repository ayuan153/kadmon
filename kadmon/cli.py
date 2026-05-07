import os

import click


def _make_provider(provider: str, model: str, aws_region: str):
    """Create the appropriate LLM provider."""
    if provider == "bedrock":
        from kadmon.providers.bedrock import BedrockProvider

        return BedrockProvider(model=model, aws_region=aws_region)
    else:
        from kadmon.providers.anthropic import AnthropicProvider

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            click.echo("Error: ANTHROPIC_API_KEY not set", err=True)
            raise SystemExit(1)
        return AnthropicProvider(model=model, api_key=api_key)


@click.group()
def main():
    """Kadmon - an LLM coding agent."""


@main.command()
@click.option("--task", required=True, type=str, help="Task description")
@click.option("--repo", default=".", type=click.Path(exists=True), help="Repository path")
@click.option("--model", default="us.anthropic.claude-sonnet-4-6", type=str, help="Model to use")
@click.option(
    "--provider",
    type=click.Choice(["anthropic", "bedrock"]),
    default="bedrock",
    help="LLM provider",
)
@click.option("--aws-region", default="us-east-1", help="AWS region for Bedrock")
def run(task: str, repo: str, model: str, provider: str, aws_region: str):
    """Run kadmon on a task."""
    from kadmon.tools import build_index, create_default_registry
    from kadmon.agent import AgentLoop

    llm = _make_provider(provider, model, aws_region)
    repo_path = os.path.abspath(repo)
    db = build_index(repo_path)
    tools = create_default_registry(repo_path, db=db)
    agent = AgentLoop(provider=llm, tools=tools)
    result = agent.run(task)
    db.close()
    if result:
        click.echo(result)
    else:
        click.echo("Agent did not produce a result.", err=True)


@main.command("eval")
@click.option("--dataset", type=click.Path(exists=True), help="Path to SWE-bench instances JSON")
@click.option("--limit", type=int, default=None, help="Max instances to run")
@click.option("--output", default="eval_results", help="Output directory")
@click.option("--model", default="claude-sonnet-4-20250514")
def eval_cmd(dataset, limit, output, model):
    """Run kadmon against SWE-bench instances."""
    import json

    from kadmon.eval import SWEBenchRunner

    if not dataset:
        click.echo("Error: --dataset required (path to instances JSON)", err=True)
        raise SystemExit(1)

    with open(dataset) as f:
        instances = json.load(f)

    if limit:
        instances = instances[:limit]

    click.echo(f"Running {len(instances)} instances with {model}...")
    runner = SWEBenchRunner(model=model)
    summary = runner.run_dataset(instances, output_dir=output)
    click.echo(
        f"\nResults: {summary.resolved}/{summary.total} resolved ({summary.resolve_rate:.1%})"
    )
    click.echo(f"Errors: {summary.errored}")
    click.echo(f"Output: {output}/")


@main.command("bench")
@click.option(
    "--languages",
    default=None,
    help="Comma-separated languages (python,javascript,go,rust,java,cpp)",
)
@click.option("--limit", type=int, default=None, help="Max exercises to run")
@click.option("--output", default="eval_results/polyglot", help="Output directory")
@click.option("--model", default="us.anthropic.claude-sonnet-4-6")
@click.option("--provider", type=click.Choice(["anthropic", "bedrock"]), default="bedrock")
@click.option("--aws-region", default="us-east-1")
@click.option("--setup/--no-setup", default=True, help="Clone exercism repos if needed")
@click.option("--workers", "-j", type=int, default=1, help="Parallel workers (default: 1)")
def bench(languages, limit, output, model, provider, aws_region, setup, workers):
    """Run Aider Polyglot benchmark."""
    from kadmon.eval.polyglot import PolyglotRunner

    langs = languages.split(",") if languages else None
    runner = PolyglotRunner(
        model=model, provider=provider, aws_region=aws_region, languages=langs, workers=workers,
    )
    if setup:
        click.echo("Setting up exercism repos...")
        runner.setup()

    click.echo(f"Running polyglot benchmark ({limit or 'all'} exercises, {workers} workers)...")
    summary = runner.run(limit=limit, output_dir=output)
    click.echo("\nResults:")
    click.echo(
        f"  Pass rate (try 1): {summary.passed_try1}/{summary.total} ({summary.pass_rate_1:.1%})"
    )
    click.echo(
        f"  Pass rate (try 2): {summary.passed_try2}/{summary.total} ({summary.pass_rate_2:.1%})"
    )
    click.echo(f"  Errors: {summary.errors}")
    click.echo(f"  Output: {output}/")
