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


@click.group(invoke_without_command=True)
@click.version_option(package_name="kadmon")
@click.pass_context
def main(ctx):
    """Kadmon - an LLM coding agent."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(chat)


@main.command()
@click.option("--model", default=None, help="Override model")
@click.option("--provider", default=None, help="Override provider")
@click.option("--aws-region", default=None, help="AWS region for Bedrock")
def chat(model, provider, aws_region):
    """Interactive chat mode (default when no subcommand given)."""
    from kadmon.memory.librarian import Librarian
    from kadmon.memory.session_tracker import SessionTracker
    from kadmon.tools import build_index, create_default_registry
    from kadmon.agent import AgentLoop
    from kadmon.human import CLIChannel
    from kadmon.cli_display import StreamDisplay

    repo_path = os.path.abspath(".")
    _provider = provider or DEFAULT_PROVIDER
    _model = model or DEFAULT_MODEL
    _region = aws_region or DEFAULT_REGION

    llm = _make_provider(_provider, _model, _region)
    db = build_index(repo_path)
    tools = create_default_registry(repo_path, db=db, provider=llm)
    librarian = Librarian(repo_path)
    session_tracker = SessionTracker(repo_path)
    channel = CLIChannel()
    display = StreamDisplay()

    click.echo("Kadmon — type your task, then press Enter. Ctrl+C to exit.\n")

    from kadmon.conversation import ConversationHistory
    conv_history = ConversationHistory(repo_path)

    task = ""
    agent = AgentLoop(
        provider=llm,
        tools=tools,
        librarian=librarian,
        session_tracker=session_tracker,
        channel=channel,
        repo_root=repo_path,
        display=display,
    )
    first_prompt = True
    try:
        while True:
            task = input("> ").strip()
            if not task:
                continue
            conv_history.snapshot(task, [], None)
            if first_prompt:
                result = agent.run(task)
                first_prompt = False
            else:
                result = agent.continue_with(task)
            if result:
                click.echo("")
            else:
                click.echo("\nDone.\n")
    except KeyboardInterrupt:
        click.echo("\nSaving session...")
        library_path = Path(repo_path) / ".kadmon" / "library"
        sessions_dir = library_path / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        current_path = sessions_dir / "current.md"
        if task:
            current_path.write_text(f"# Interrupted Session\n\nLast task: {task}\n")
        click.echo("Session saved. Use 'kadmon continue' to resume.")
    except EOFError:
        click.echo("\nBye.")
    finally:
        db.close()


@main.command("continue")
@click.option("--model", default=None, help="Override model")
@click.option("--provider", default=None, help="Override provider")
@click.option("--aws-region", default=None, help="AWS region for Bedrock")
def continue_session(model, provider, aws_region):
    """Resume the previous task from sessions/current.md."""
    from kadmon.memory.librarian import Librarian
    from kadmon.memory.session_tracker import SessionTracker
    from kadmon.tools import build_index, create_default_registry
    from kadmon.agent import AgentLoop
    from kadmon.human import CLIChannel
    from kadmon.cli_display import StreamDisplay

    repo_path = os.path.abspath(".")
    _provider = provider or DEFAULT_PROVIDER
    _model = model or DEFAULT_MODEL
    _region = aws_region or DEFAULT_REGION

    library_path = Path(repo_path) / ".kadmon" / "library"
    current_path = library_path / "sessions" / "current.md"

    if not current_path.exists() or not current_path.read_text().strip():
        click.echo("No saved session found. Nothing to continue.")
        raise SystemExit(1)

    task = current_path.read_text()
    click.echo("Resuming session...\n")

    llm = _make_provider(_provider, _model, _region)
    db = build_index(repo_path)
    tools = create_default_registry(repo_path, db=db, provider=llm)
    librarian = Librarian(repo_path)
    session_tracker = SessionTracker(repo_path)
    channel = CLIChannel()
    display = StreamDisplay()

    agent = AgentLoop(
        provider=llm,
        tools=tools,
        librarian=librarian,
        session_tracker=session_tracker,
        channel=channel,
        repo_root=repo_path,
        display=display,
    )
    result = agent.run(task)
    db.close()
    if result:
        click.echo(result)
    else:
        click.echo("\nDone.\n")


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
    tools = create_default_registry(repo_path, db=db, provider=llm)
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
@click.option("--repo", default=".", type=click.Path(exists=True), help="Repository path")
@click.option("--global", "show_global", is_flag=True, help="Show sessions across all projects")
def status(repo: str, show_global: bool):
    """Show current session state and library summary."""
    if show_global:
        from kadmon.memory.central_index import CentralIndex
        index = CentralIndex()
        sessions = index.list_recent(days=14)
        if not sessions:
            click.echo("No recent sessions found across projects.")
            return
        click.echo("\n=== Recent Sessions (last 14 days) ===\n")
        for s in sessions:
            status_icon = {"in_progress": "⏳", "completed": "✓", "handed_off": "↗"}.get(s.status, s.status)
            click.echo(f"  {status_icon} [{s.session_key}] {s.task}")
            click.echo(f"    Repo: {s.repo}")
            click.echo(f"    Updated: {s.last_updated}")
            click.echo("")
        return

    from kadmon.memory.session_tracker import SessionTracker

    repo_path = os.path.abspath(repo)
    kadmon_dir = Path(repo_path) / ".kadmon"

    if not kadmon_dir.exists():
        click.echo("No .kadmon directory found. Run 'kadmon init' or start a task first.")
        return

    # --- Session status ---
    tracker = SessionTracker(repo_path)
    session = tracker.load()

    click.echo("\n=== Kadmon Status ===\n")

    if session is None:
        click.echo("Session:   no active session")
    else:
        status_icon = {"in_progress": "⏳", "completed": "✓", "handed_off": "↗"}.get(
            session.status, session.status
        )
        click.echo(f"Session:   {session.session_id}  [{status_icon} {session.status}]")
        click.echo(f"Started:   {session.started}")
        click.echo(f"Task:      {session.task}")

        delegations = session.delegations
        if delegations:
            click.echo(f"\nDelegations ({len(delegations)}):")
            for d in delegations:
                icon = {"completed": "✓", "failed": "✗", "in_progress": "⏳"}.get(d.status, d.status)
                line = f"  {icon} [{d.id}] {d.task}"
                if d.summary:
                    line += f"\n       → {d.summary}"
                click.echo(line)
        else:
            click.echo("\nDelegations: none")

    # --- Library summary ---
    library_path = kadmon_dir / "library"
    click.echo("")
    if not library_path.exists():
        click.echo("Library:   empty (no .kadmon/library/ yet)")
    else:
        index_path = library_path / "index.md"
        if index_path.exists() and index_path.stat().st_size > 0:
            click.echo("Library:")
            for line in index_path.read_text().splitlines():
                if line.strip() and not line.startswith("#"):
                    click.echo(f"  {line.strip()}")
        else:
            files = list(library_path.glob("*.md"))
            if files:
                click.echo(f"Library:   {len(files)} file(s) in .kadmon/library/")
            else:
                click.echo("Library:   empty")

        # Session history count
        sessions_dir = kadmon_dir / "sessions"
        if sessions_dir.exists():
            count = len(list(sessions_dir.glob("*.json")))
            if count:
                click.echo(f"\nHistory:   {count} archived session(s) in .kadmon/sessions/")

    # --- Session history (always check, independent of library) ---
    sessions_dir = kadmon_dir / "sessions"
    if sessions_dir.exists():
        count = len(list(sessions_dir.glob("*.json")))
        if count:
            click.echo(f"\nHistory:   {count} archived session(s)")

    click.echo("")


@main.command()
@click.option("--with-files", is_flag=True, help="Also rollback file changes")
def rewind(with_files: bool):
    """Rewind conversation to a previous prompt."""
    from kadmon.conversation import ConversationHistory

    repo_path = os.path.abspath(".")
    history = ConversationHistory(repo_path)
    turns = history.list_turns()
    if not turns:
        click.echo("No conversation history to rewind to.")
        return
    click.echo("\nRecent prompts:")
    for t in turns:
        click.echo(f"  [{t['turn_id']}] \"{t['prompt']}\"")
    click.echo("")
    choice = click.prompt("Rewind to before which prompt?", type=int)
    turn = history.rewind(choice)
    if not turn:
        click.echo(f"Turn {choice} not found.")
        return
    if with_files:
        from kadmon.checkpoints import CheckpointManager

        mgr = CheckpointManager(repo_path)
        for cp in mgr.list():
            if cp["timestamp"] > turn.timestamp:
                mgr.rollback(cp["id"])
    click.echo(f"\u2713 Conversation restored to before prompt {choice}. {'Files also restored.' if with_files else 'Files unchanged.'}")
    click.echo("Start kadmon to continue from this point.")


@main.command()
@click.argument("checkpoint_id", required=False)
def rollback(checkpoint_id):
    """Rollback file changes to a checkpoint."""
    from kadmon.checkpoints import CheckpointManager

    repo_path = os.path.abspath(".")
    mgr = CheckpointManager(repo_path)
    restored = mgr.rollback(checkpoint_id)
    if not restored:
        click.echo("No checkpoint to rollback to.")
        return
    click.echo(f"\u2713 Restored {len(restored)} file(s):")
    for f in restored:
        click.echo(f"  {f}")


@main.command()
def checkpoints():
    """List available file checkpoints."""
    from kadmon.checkpoints import CheckpointManager

    repo_path = os.path.abspath(".")
    mgr = CheckpointManager(repo_path)
    cps = mgr.list()
    if not cps:
        click.echo("No checkpoints available.")
        return
    click.echo("\nCheckpoints:")
    for cp in cps:
        files = ", ".join(cp["files"])
        click.echo(f"  [{cp['id']}] {cp['tool']} \u2014 {files}")
    click.echo("")


@main.command()
def init():
    """Interactive setup — configure provider, credentials, and test connection."""
    click.echo("\n✨ Kadmon Setup\n")

    # 1. Pick provider
    click.echo("Choose your LLM provider:")
    click.echo("  1. Anthropic (API key)")
    click.echo("  2. OpenAI (API key)")
    click.echo("  3. Google Gemini (API key)")
    click.echo("  4. AWS Bedrock (uses AWS credentials)")
    choice = click.prompt("Provider", type=click.Choice(["1", "2", "3", "4"]), default="1")

    provider_map = {"1": "anthropic", "2": "openai", "3": "gemini", "4": "bedrock"}
    provider = provider_map[choice]

    # 2. Configure credentials
    config = {"provider": provider}

    if provider == "anthropic":
        config["api_key"] = click.prompt("Anthropic API key", hide_input=True)
        config["model"] = click.prompt("Model", default="claude-sonnet-4-20250514")
    elif provider == "openai":
        config["api_key"] = click.prompt("OpenAI API key", hide_input=True)
        config["model"] = click.prompt("Model", default="gpt-4o")
    elif provider == "gemini":
        config["api_key"] = click.prompt("Google API key", hide_input=True)
        config["model"] = click.prompt("Model", default="gemini-2.5-flash")
    elif provider == "bedrock":
        config["aws_region"] = click.prompt("AWS region", default="us-east-1")
        config["aws_profile"] = click.prompt(
            "AWS profile (leave empty for default credentials)", default="", show_default=False
        )
        config["model"] = click.prompt("Model", default="us.anthropic.claude-sonnet-4-6")

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
