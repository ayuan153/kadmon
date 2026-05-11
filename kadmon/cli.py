import os
from pathlib import Path

import click

from kadmon.config import DEFAULT_MODEL, DEFAULT_PROVIDER, DEFAULT_REGION


def _make_provider(provider: str, model: str, aws_region: str):
    """Create the appropriate LLM provider."""
    if provider == "bedrock":
        from kadmon.providers.bedrock import BedrockProvider

        return BedrockProvider(model=model, aws_region=aws_region)
    elif provider == "openai":
        from kadmon.providers.openai_provider import OpenAIProvider

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            click.echo("Error: OPENAI_API_KEY not set", err=True)
            raise SystemExit(1)
        return OpenAIProvider(model=model, api_key=api_key)
    elif provider == "gemini":
        from kadmon.providers.gemini import GeminiProvider

        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            click.echo("Error: GOOGLE_API_KEY not set", err=True)
            raise SystemExit(1)
        return GeminiProvider(model=model, api_key=api_key)
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
@click.option("--model", default=DEFAULT_MODEL, type=str, help="Model to use")
@click.option(
    "--provider",
    type=click.Choice(["anthropic", "bedrock", "openai", "gemini"]),
    default=DEFAULT_PROVIDER,
    help="LLM provider",
)
@click.option("--aws-region", default=DEFAULT_REGION, help="AWS region for Bedrock")
@click.option(
    "--mode",
    type=click.Choice(["yolo", "cautious", "paranoid"]),
    default="cautious",
    help="Agent mode",
)
def run(task: str, repo: str, model: str, provider: str, aws_region: str, mode: str):
    """Run kadmon on a task."""
    from kadmon.tools import build_index, create_default_registry
    from kadmon.agent import AgentLoop
    from kadmon.memory.librarian import Librarian
    from kadmon.memory.session_tracker import SessionTracker
    from kadmon.human import CLIChannel

    llm = _make_provider(provider, model, aws_region)
    repo_path = os.path.abspath(repo)
    db = build_index(repo_path)
    tools = create_default_registry(repo_path, db=db)
    librarian = Librarian(repo_path)
    session_tracker = SessionTracker(repo_path)
    channel = CLIChannel() if mode != "yolo" else None
    agent = AgentLoop(
        provider=llm,
        tools=tools,
        librarian=librarian,
        session_tracker=session_tracker,
        mode=mode,
        channel=channel,
        repo_root=repo_path,
    )
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
@click.option("--model", default=DEFAULT_MODEL)
@click.option("--provider", type=click.Choice(["anthropic", "bedrock", "openai", "gemini"]), default=DEFAULT_PROVIDER)
@click.option("--aws-region", default=DEFAULT_REGION)
@click.option("--setup/--no-setup", default=True, help="Clone exercism repos if needed")
@click.option("--workers", "-j", type=int, default=4, help="Parallel workers (default: 4)")
def bench(languages, limit, output, model, provider, aws_region, setup, workers):
    """Run Aider Polyglot benchmark."""
    from kadmon.eval.polyglot import PolyglotRunner

    langs = languages.split(",") if languages else None
    runner = PolyglotRunner(
        model=model,
        provider=provider,
        aws_region=aws_region,
        languages=langs,
        workers=workers,
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


@main.command()
def init():
    """Interactive setup — configure provider, credentials, and test connection."""
    click.echo("\n✨ Kadmon Setup\n")

    # 1. Pick provider
    click.echo("Choose your LLM provider:")
    click.echo("  1. AWS Bedrock (recommended — uses your AWS credentials)")
    click.echo("  2. Anthropic (direct API key)")
    click.echo("  3. OpenAI")
    choice = click.prompt("Provider", type=click.Choice(["1", "2", "3"]), default="1")

    provider_map = {"1": "bedrock", "2": "anthropic", "3": "openai"}
    provider = provider_map[choice]

    # 2. Configure credentials
    config = {"provider": provider}

    if provider == "bedrock":
        config["aws_region"] = click.prompt("AWS region", default="us-east-1")
        config["aws_profile"] = click.prompt(
            "AWS profile (leave empty for default credentials)", default="", show_default=False
        )
        config["model"] = click.prompt("Model", default="us.anthropic.claude-sonnet-4-6")
    elif provider == "anthropic":
        config["api_key"] = click.prompt("Anthropic API key", hide_input=True)
        config["model"] = click.prompt("Model", default="claude-sonnet-4-20250514")
    elif provider == "openai":
        config["api_key"] = click.prompt("OpenAI API key", hide_input=True)
        config["model"] = click.prompt("Model", default="gpt-4o")

    # 3. Test connection
    click.echo("\nTesting connection...")
    try:
        _test_connection(config)
        click.echo("✓ Connection successful!")
    except Exception as e:
        click.echo(f"✗ Connection failed: {e}", err=True)
        if not click.confirm("Save config anyway?"):
            raise SystemExit(1)

    # 4. Save config
    config_dir = Path(".") / ".kadmon"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    _write_config(config_path, config)

    click.echo(f"\n✓ Config saved to {config_path}")
    click.echo("\nYou're ready! Try:")
    click.echo('  kadmon run --task "Describe what this project does"')


def _test_connection(config: dict):
    """Make a minimal API call to verify credentials work."""
    provider = config["provider"]
    model = config["model"]

    if provider == "bedrock":
        if config.get("aws_profile"):
            os.environ["AWS_PROFILE"] = config["aws_profile"]
        from kadmon.providers.bedrock import BedrockProvider

        p = BedrockProvider(model=model, aws_region=config.get("aws_region", "us-east-1"))
    elif provider == "anthropic":
        from kadmon.providers.anthropic import AnthropicProvider

        p = AnthropicProvider(model=model, api_key=config["api_key"])
    elif provider == "openai":
        if not config.get("api_key", "").startswith("sk-"):
            raise ValueError("Invalid API key format")
        return
    else:
        return

    from kadmon.providers.base import Message

    p.complete(messages=[Message(role="user", content="Say 'ok'")], system="Respond with just 'ok'")


def _write_config(path: Path, config: dict):
    """Write config as TOML."""
    lines = ["# Kadmon configuration", "# Generated by: kadmon init", ""]
    lines.append("[provider]")
    lines.append(f'name = "{config["provider"]}"')
    lines.append(f'model = "{config["model"]}"')

    if config.get("aws_region"):
        lines.append(f'aws_region = "{config["aws_region"]}"')
    if config.get("aws_profile"):
        lines.append(f'aws_profile = "{config["aws_profile"]}"')
    if config.get("api_key"):
        lines.append(f'api_key = "{config["api_key"]}"')

    lines.append("")
    lines.append("[agent]")
    lines.append('mode = "yolo"  # yolo | cautious | paranoid')
    lines.append("")
    path.write_text("\n".join(lines) + "\n")
