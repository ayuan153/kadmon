# Kadmon

**YOLO mode you can trust.** An autonomous coding agent that manages its own context, asks the right questions, and proves its work.

## Why Kadmon exists

Current AI coding agents get context management wrong. They run until the context window fills up, then try to recover with compaction — lossy summarization that throws away critical information mid-task. Human-in-the-loop checks are aimed at the wrong level: agents ask for permission on mechanics (file edits, shell commands) when what they should be probing for is *directional* feedback.

Kadmon is built on a different philosophy:

- **Minimize token usage from the start.** Delegate specialized subtasks to focused subagents with scoped context instead of stuffing everything into one session. Use persistent memory across sessions, not just within them.
- **Hand off context gracefully.** As a session grows, Kadmon plans handoff points — packaging completed work, decisions made, and open questions into a clean context for the next phase. No lossy compaction.
- **Go fast on mechanics, go slow on direction.** Kadmon doesn't ask "can I edit this file?" It asks "we could approach this as a refactor or a rewrite — here's the tradeoff, which direction do you want?" Agents should automate execution and surface strategic decisions.

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

This walks you through provider setup once (globally — not per-project). Then in any project:

```bash
cd your-project
kadmon
```

Type your task, kadmon works, streams output as it goes. Ctrl+C to exit.

### Updating

```bash
pip install --upgrade kadmon
```

Or with npm:
```bash
npm update -g kadmon
```

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

Config is saved to `.kadmon/config.toml` after `kadmon init` — you only set this up once.

## What Makes Kadmon Different

Other agents are either fast-but-reckless (YOLO mode, guess and go) or safe-but-slow (approve every file write). Kadmon is neither. It's fully autonomous on mechanics — but asks you when it's genuinely uncertain about direction.

### YOLO on execution, deliberate on decisions

Kadmon never asks "can I edit this file?" or "should I run this test?" — it just does it. But when requirements are ambiguous, when a design could go two ways, when it's not sure what you actually want — it asks. This is what makes it trustworthy enough to run unsupervised.

### Self-managing context

Most agents degrade over long sessions. Context fills up with irrelevant tool outputs, the model starts looping, quality drops. You restart, lose everything, re-explain the task.

Kadmon detects this happening and handles it:
1. Writes a focused handoff document (what's done, what's next, key pointers)
2. Clears its own context
3. Continues from the handoff — no human intervention needed

### Persistent memory across sessions

Kadmon maintains a project library (`.kadmon/library/`) that survives across sessions:
- Architecture notes, conventions, decisions — written by the agent, not by you
- Mechanical session logging captures everything (flight recorder)
- LLM-powered curation synthesizes raw logs into clean knowledge between sessions
- Cross-project session index so kadmon knows what you were working on yesterday

### Checkpoints and rewind

Made a wrong turn? Two escape hatches:
- `kadmon rewind` — go back to before any recent prompt (conversation reset, files untouched)
- `kadmon rollback` — undo file changes to any checkpoint

The agent also uses checkpoints autonomously: edit → test → fail → rollback → try differently. No human intervention needed for routine recovery.

## Commands

```bash
kadmon                    # Interactive chat (default)
kadmon continue           # Resume previous task from where you left off
kadmon status             # Show current session and library state
kadmon status --global    # Show recent sessions across all projects
kadmon rewind             # Rewind conversation to a previous prompt
kadmon rollback [id]      # Rollback file changes to a checkpoint
kadmon checkpoints        # List available file checkpoints
kadmon init               # Interactive provider setup
kadmon run --task "..."   # One-shot mode
```

## Architecture

```
kadmon/
├── agent/       # ReAct loop, planning, handoff, recovery
├── providers/   # LLM providers (Bedrock, Anthropic, OpenAI, Gemini)
├── tools/       # file I/O, search, shell, plan, ask_human, library, checkpoints, parallel
├── memory/      # Library team (index/read/write/prune/curator agents), session log
├── human/       # Question batching, CLI/webhook channels
├── workers.py   # Parallel task dispatch (ThreadPoolExecutor)
├── checkpoints.py  # File-level snapshots for rollback
├── conversation.py # Conversation state for rewind
├── eval/        # Benchmark harnesses (Aider Polyglot, SWE-bench)
└── index/       # Tree-sitter symbol index (SQLite)
```

Key design:
- **Architect/Editor phase separation** — explore and plan first, then execute step by step
- **Library Team** — focused LLM subagents for on-demand context retrieval (not blob injection)
- **Dual-layer persistence** — mechanical capture (JSONL flight recorder) + intelligent curation (LLM synthesis)
- **Autonomous handoff** — detects context degradation, writes handoff, resets, continues
- **Parallel workers** — fan out independent subtasks to separate context windows
- **No frameworks** — provider SDKs directly, minimal core
- **ask_human as a tool** — always available for genuine uncertainty, never for permission

## Philosophy

Kadmon optimizes for **trust**, not speed.

The bet: developers give more autonomy to an agent that asks "should this be REST or GraphQL?" before building the wrong thing — and then proves it works with passing tests — than to one that silently builds the wrong thing fast.

Trust compounds. An agent that asks good questions and verifies its work earns the right to run unsupervised on bigger tasks. An agent that guesses and sprints earns Ctrl+C.

## Local Development

```bash
git clone https://github.com/ayuan153/kadmon.git
cd kadmon
./dev
```

`./dev` handles everything: creates a venv, installs dependencies, and launches kadmon from your local source.

```bash
./dev              # Launch interactive kadmon (local build)
./dev bench        # 5 Python exercises
./dev bench 20     # 20 exercises
./dev bench-full   # All 225 exercises, 6 languages
./dev run "task"   # One-shot mode
./dev test         # Run tests
./dev lint         # Run linter
```

## Benchmarking

### Aider Polyglot

225 Exercism exercises across Python, JavaScript, Go, Rust, Java, C++.

```bash
kadmon bench --languages python --limit 5   # Quick smoke test
kadmon bench --languages python              # Full Python
kadmon bench -j 10                           # All languages, parallel
```

### SWE-bench

```bash
kadmon eval --dataset swe_bench_verified_mini.json --limit 10
```

## Contributing

See [AGENTS.md](AGENTS.md) for AI contribution guidelines. Key rules:
- Build → Lint → Test → Commit (no skipping)
- Conventional commits with scopes
- One concern per commit

## Publishing

```bash
./publish          # patch: 0.4.0 → 0.4.1
./publish minor    # minor: 0.4.1 → 0.5.0
./publish major    # major: 0.5.0 → 1.0.0
```

Bumps version, commits, tags, pushes. CI publishes to PyPI + npm automatically.

## License

MIT
