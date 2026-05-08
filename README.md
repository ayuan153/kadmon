# Kadmon

An autonomous coding agent that manages its own context, asks clarifying questions, and hands off between sessions without human intervention. Scores 100% on Aider Polyglot (Python) benchmark.

## Install

```bash
pip install kadmon
```

## Getting Started

```bash
# Interactive setup — picks your provider, configures credentials, tests the connection
kadmon init

# Run on a repo
cd your-project
kadmon run --task "Fix the failing test in test_auth.py"
```

`kadmon init` walks you through:
1. Choose provider (Bedrock, Anthropic, OpenAI)
2. Configure credentials (AWS profile, API key, etc.)
3. Test the connection
4. Save to `.kadmon/config.toml`

### Manual Provider Setup

If you prefer to skip `kadmon init`:

**AWS Bedrock** (default):
```bash
# Any standard AWS credential method works (SSO, env vars, profiles)
export AWS_PROFILE=your-profile
export AWS_REGION=us-east-1
kadmon run --task "..." --provider bedrock --model us.anthropic.claude-sonnet-4-6
```

**Anthropic Direct**:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
kadmon run --task "..." --provider anthropic --model claude-sonnet-4-20250514
```

**OpenAI**:
```bash
export OPENAI_API_KEY=sk-...
kadmon run --task "..." --provider openai --model gpt-4o
```

## What Makes Kadmon Different

Most coding agents are "very talented junior engineers" — they need constant supervision and context management. Kadmon is designed to be piloted like a **team lead manages a senior engineer**:

1. **No guessing** — asks clarifying questions when requirements are ambiguous (not for permission — for correctness)
2. **Rock climbing** — verifies each step before moving to the next, never sprints into the void
3. **Self-managing context** — detects when its context is degrading, writes a handoff doc, and continues in a fresh session automatically

### Autonomous Context Management

```
.kadmon/
├── config.toml          # Provider config, preferences
├── library/             # Persistent knowledge (survives across sessions)
│   ├── architecture.md  # Project structure notes
│   ├── conventions.md   # Patterns, gotchas
│   └── tasks/current.md # Active task state
├── session.json         # What's in flight right now
├── handoffs/            # Handoff docs (context continuity)
└── symbols.db           # Code structure index (tree-sitter)
```

The agent automatically:
- Loads relevant library context on startup (cold start)
- Saves learnings after each completed step
- Detects context degradation (token budget, loops, quality drop)
- Writes a structured handoff and resets — no human intervention needed

## Local Development

```bash
# Clone and install in dev mode
git clone https://github.com/ayuan153/kadmon.git
cd kadmon
pip install -e ".[dev]"

# Run tests
./dev test

# Lint
./dev lint

# Run kadmon against a local repo
./dev run "Fix the bug in parser.py"

# Benchmark (5 Python exercises, quick smoke test)
./dev bench

# Full benchmark (225 exercises, all languages)
./dev bench-full
```

### Dev Script Reference

```bash
./dev bench [N]     # N Python exercises (default: 5)
./dev bench-full    # All 225 exercises, 6 languages
./dev run "task"    # Run kadmon on current repo
./dev test          # pytest
./dev lint          # ruff
```

### Running Against Your Own Code

```bash
# From any repo:
kadmon run --task "Add input validation to the create_user endpoint"

# With planning disabled (faster, simpler loop — good for debugging):
kadmon run --task "Fix the typo in README.md" --no-planning

# In yolo mode (no tool approval gates):
kadmon run --task "Refactor the auth module" --mode yolo
```

## Benchmarking

### Aider Polyglot

225 Exercism exercises across Python, JavaScript, Go, Rust, Java, C++.

```bash
# Quick smoke test (~$1)
kadmon bench --languages python --limit 5

# Full Python
kadmon bench --languages python

# All languages, 10 parallel workers
kadmon bench -j 10

# Sequential (live timer, good for debugging)
kadmon bench --limit 5 -j 1
```

Results: `eval_results/polyglot/summary.json`

### SWE-bench

```bash
kadmon eval --dataset swe_bench_verified_mini.json --limit 10
```

## Architecture

```
kadmon/
├── agent/       # ReAct loop, planning, backtracking, handoff, pruner
├── providers/   # LLM providers (Bedrock, Anthropic, OpenAI)
├── tools/       # file I/O, search, shell, skeleton, references, plan, ask_human
├── human/       # Question batching, CLI/webhook channels
├── eval/        # Benchmark harnesses (Aider Polyglot, SWE-bench)
├── index/       # Tree-sitter symbol index (SQLite)
└── memory/      # Librarian, session tracker, read cache
```

Key design:
- **Single-threaded ReAct loop** with architect/editor phase separation
- **No frameworks** — provider SDKs directly, minimal core
- **Autonomous handoff** — detects context degradation, resets with continuity
- **File-based memory** — `.kadmon/library/` persists knowledge across sessions
- **Ambiguity resolution** — `ask_human` tool for genuine uncertainty (not permission)

## Configuration

All defaults in `kadmon/config.py`:

```python
DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-6"
DEFAULT_PROVIDER = "bedrock"
DEFAULT_REGION = "us-east-1"
```

Per-project config at `.kadmon/config.toml` (created by `kadmon init`).

## Contributing

See [AGENTS.md](AGENTS.md) for AI contribution guidelines. Key rules:
- Build → Lint → Test → Commit (no skipping)
- Conventional commits with scopes
- One concern per commit

## License

MIT
