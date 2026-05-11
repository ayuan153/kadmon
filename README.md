# Kadmon

An autonomous coding agent that manages its own context, asks clarifying questions, and hands off between sessions without human intervention. Scores 100% on Aider Polyglot (Python) benchmark.

## Install

```bash
npm install -g kadmon
```

Or with pip:
```bash
pip install kadmon
```

## Getting Started

```bash
kadmon init
```

This walks you through provider setup interactively. Then just:

```bash
cd your-project
kadmon
```

Type your task, kadmon works, streams output as it goes. Ctrl+C to exit.

### Provider Setup (manual alternative to `kadmon init`)

**Anthropic:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
kadmon --provider anthropic
```

**OpenAI:**
```bash
export OPENAI_API_KEY=sk-...
kadmon --provider openai
```

**Google Gemini:**
```bash
export GOOGLE_API_KEY=...
kadmon --provider gemini
```

**AWS Bedrock:**
```bash
export AWS_PROFILE=your-profile
export AWS_REGION=us-east-1
kadmon --provider bedrock
```

Config is saved to `.kadmon/config.toml` after `kadmon init` — you only set this up once per project.

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
git clone https://github.com/ayuan153/kadmon.git
cd kadmon
./dev
```

That's it. `./dev` handles everything: creates a venv, installs dependencies, and launches kadmon from your local source. First run takes ~30s for setup, subsequent runs are instant.

```bash
./dev              # Launch interactive kadmon (local build)
./dev bench        # 5 Python exercises
./dev bench 20     # 20 exercises
./dev bench-full   # All 225 exercises, 6 languages
./dev run "task"   # One-shot mode
./dev test         # Run tests
./dev lint         # Run linter
./dev setup        # Force reinstall deps
```

The global `kadmon` command (from `npm install -g kadmon`) runs the published release. `./dev` always runs your local source. No conflicts.

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

## Publishing

```bash
./publish          # patch: 0.1.0 → 0.1.1
./publish minor    # minor: 0.1.1 → 0.2.0
./publish major    # major: 0.2.0 → 1.0.0
```

Bumps version, commits, tags, pushes. CI publishes to PyPI + npm automatically.

## License

MIT
