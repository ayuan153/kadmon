# Kadmon

A coding agent that solves software engineering tasks autonomously. Targets top performance on SWE-bench and Aider Polyglot benchmarks through scaffolding excellence — not model dependence.

## Architecture

```
kadmon/
├── agent/       # ReAct loop, planning, backtracking, architect/editor modes
├── providers/   # LLM providers (Anthropic direct, AWS Bedrock)
├── tools/       # Agent tools (file I/O, search, shell, skeleton, references)
├── eval/        # Benchmark harnesses (SWE-bench, Aider Polyglot)
├── index/       # Tree-sitter symbol index (SQLite, incremental)
└── memory/      # Read cache, cross-session memory
```

Key design choices:
- **Single-threaded ReAct loop** with architect/editor phase separation
- **SQLite symbol index** with tree-sitter for structural code understanding
- **Hash-based read dedup** to minimize token waste on re-reads
- **Loop detection + backtracking** with git-based checkpoints
- **No frameworks** — provider SDKs directly, ~100-line core loop

## Quick Start (with Bedrock)

```bash
# One-time setup: add 'kadmon' profile to ~/.aws/config
# (already done if you cloned this repo and ran setup)
cat >> ~/.aws/config << 'EOF'
[profile kadmon]
credential_process=your-credential-tool --account YOUR_ACCOUNT --role YourRole
region=us-east-1
EOF

# Install
pip install -e ".[dev]"

# Smoke test (5 Python exercises, ~$1)
./dev bench

# Run on a repo
./dev run "Fix the TypeError in utils.py"

# Unit tests
./dev test
```

## Setup

```bash
git clone https://github.com/ayuan153/kadmon.git
cd kadmon
pip install -e ".[dev]"
```

### Prerequisites

- Python 3.11+
- An LLM provider:
  - **Anthropic direct**: `export ANTHROPIC_API_KEY=sk-ant-...`
  - **AWS Bedrock**: configured AWS credentials (`aws configure` or env vars)

### For benchmarking (language test runners)

```bash
# Python exercises
pip install pytest

# Go exercises
# (go must be installed)

# Rust exercises
# (cargo must be installed)

# JavaScript exercises
# (node + npm must be installed)

# Java exercises
# (JDK + gradle must be installed)

# C++ exercises
# (cmake + make must be installed)
```

## Usage

### Run on a task

```bash
# Using Anthropic directly
kadmon run --task "Fix the TypeError in utils.py" --repo /path/to/repo

# Using AWS Bedrock
kadmon run --task "Fix the TypeError in utils.py" --repo /path/to/repo \
  --provider bedrock --model global.anthropic.claude-sonnet-4-6-v1

# Specify model
kadmon run --task "Add input validation to the /users endpoint" --repo . \
  --model claude-sonnet-4-20250514
```

The agent will:
1. Build a symbol index of the repo (first run takes a few seconds)
2. Explore the codebase (architect phase)
3. Create a plan
4. Execute edits and verify with tests (editor phase)
5. Output the final git diff patch

### Manual testing

Quick smoke test against a real repo:

```bash
# Clone a test repo
git clone https://github.com/pallets/flask.git /tmp/flask-test
cd /tmp/flask-test
git checkout 2.3.x

# Run kadmon on a simple task
kadmon run --task "Add a docstring to the Flask.make_response method in src/flask/app.py" \
  --repo . --provider bedrock
```

Test with planning disabled (simpler, faster, good for debugging):

```bash
# The agent uses a simple ReAct loop without architect/editor separation
# Useful for quick iteration on prompts and tool behavior
kadmon run --task "Fix the typo in README.md" --repo . --provider anthropic
```

## Benchmarking

### Aider Polyglot (recommended for iteration)

225 Exercism exercises across 6 languages. ~$16-27 per full run with Sonnet.

```bash
# Quick smoke test (5 Python exercises, ~$1)
kadmon bench --languages python --limit 5 --provider bedrock

# Full Python only (~$3-5)
kadmon bench --languages python --provider bedrock

# Full benchmark, all languages (~$16-27)
kadmon bench --provider bedrock --model global.anthropic.claude-sonnet-4-6-v1

# Skip repo cloning if already set up
kadmon bench --no-setup --languages python --limit 10
```

Results are saved to `eval_results/polyglot/`:
- `summary.json` — pass rates and totals
- `{lang}_{exercise}.json` — per-exercise results

Key metrics:
- **pass_rate_1**: exercises solved on first attempt
- **pass_rate_2**: exercises solved within 2 attempts (comparable to Aider leaderboard)

### SWE-bench

Run against SWE-bench instances (requires a JSON file of instances):

```bash
# Run 10 instances
kadmon eval --dataset swe_bench_verified_mini.json --limit 10 --provider bedrock

# Full run
kadmon eval --dataset swe_bench_verified.json --provider bedrock \
  --model global.anthropic.claude-sonnet-4-6-v1
```

Results saved to `eval_results/` with per-instance patches and a summary.

## Development

### Build & test loop

```bash
# Lint
ruff check kadmon/ tests/

# Run tests (61 tests)
pytest tests/ -v

# Run a specific test file
pytest tests/test_planning.py -v
```

### Project structure

| Module | Purpose |
|--------|---------|
| `kadmon/agent/loop.py` | Core ReAct loop with architect/editor phases |
| `kadmon/agent/planner.py` | Plan data structure and step tracking |
| `kadmon/agent/prompts.py` | System prompts for each mode |
| `kadmon/agent/recovery.py` | Loop detection (repeated actions/errors) |
| `kadmon/agent/backtrack.py` | Plan-aware backtracking with checkpoints |
| `kadmon/tools/` | All agent tools (file_io, search, shell, skeleton, references, plan) |
| `kadmon/index/` | SQLite symbol index + tree-sitter parser |
| `kadmon/providers/` | LLM provider abstraction (Anthropic, Bedrock) |
| `kadmon/eval/` | Benchmark harnesses |

### Adding a new tool

1. Create `kadmon/tools/your_tool.py` extending `Tool`
2. Define `name`, `description`, `parameters` (JSON Schema), `execute()`
3. Register in `kadmon/tools/__init__.py` → `create_default_registry()`
4. Add tests in `tests/`
5. Run `ruff check && pytest`

### Commit convention

[Conventional Commits](https://www.conventionalcommits.org/) with scopes:

```
feat(tools): add rename_symbol tool
fix(agent): prevent infinite loop on repeated edit failures
test(eval): add polyglot benchmark edge cases
```

See [AGENTS.md](AGENTS.md) for full contribution guidelines.

## CLI Reference

```
kadmon run      Run the agent on a task
kadmon bench    Run Aider Polyglot benchmark
kadmon eval     Run SWE-bench evaluation

Options (all commands):
  --model         LLM model name
  --provider      anthropic | bedrock
  --aws-region    AWS region for Bedrock (default: us-west-2)

kadmon run:
  --task          Task description (required)
  --repo          Repository path (default: .)

kadmon bench:
  --languages     Comma-separated: python,javascript,go,rust,java,cpp
  --limit         Max exercises to run
  --output        Output directory
  --setup/--no-setup  Clone exercism repos if needed

kadmon eval:
  --dataset       Path to SWE-bench instances JSON
  --limit         Max instances to run
  --output        Output directory
```

## License

MIT
