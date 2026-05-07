# Kadmon

A coding agent that solves software engineering tasks autonomously. Targets top performance on SWE-bench and Aider Polyglot benchmarks through scaffolding excellence — not model dependence.

## Quick Start

```bash
git clone https://github.com/ayuan153/kadmon.git
cd kadmon
pip install -e ".[dev]"

# Run benchmark (5 Python exercises, ~$1)
./dev bench

# Run on a repo
./dev run "Fix the TypeError in utils.py"

# Unit tests
./dev test
```

### AWS Setup (one-time)

Kadmon uses Bedrock by default. Configure AWS credentials however you prefer:

```bash
# Option A: SSO
aws configure sso

# Option B: credential process in ~/.aws/config
[profile kadmon]
credential_process=your-credential-tool --account YOUR_ACCOUNT --role YourRole
region=us-east-1

# Option C: environment variables
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
```

Set `AWS_PROFILE=kadmon` (or your profile name) before running kadmon.

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

## Dev Script

The `./dev` script is the primary interface for development:

```bash
./dev bench        # 5 Python exercises (quick smoke test)
./dev bench 20     # 20 Python exercises
./dev bench-full   # All 225 exercises, all 6 languages
./dev run "task"   # Run kadmon on current repo
./dev test         # Unit tests
./dev lint         # Ruff linter
```

Override defaults with env vars:
```bash
KADMON_MODEL=us.anthropic.claude-opus-4-6 ./dev bench
AWS_PROFILE=other-profile ./dev bench
```

## Benchmarking

### Aider Polyglot

225 Exercism exercises across 6 languages (Python, JS, Go, Rust, Java, C++). Runs 4 workers in parallel by default.

```bash
# Quick iteration
./dev bench 10

# Full run (~$20, comparable to Aider leaderboard)
./dev bench-full

# More parallelism (default: 4 workers)
kadmon bench -j 10

# Specific languages
kadmon bench --languages python,javascript --limit 20

# Sequential mode for debugging (live timer per exercise)
kadmon bench --limit 5 -j 1
```

Results saved to `eval_results/polyglot/`:
- `summary.json` — pass rates and totals
- `{lang}_{exercise}.json` — per-exercise results

Key metrics:
- **pass_rate_1**: solved on first attempt
- **pass_rate_2**: solved within 2 attempts (Aider leaderboard metric)

### SWE-bench

```bash
kadmon eval --dataset swe_bench_verified_mini.json --limit 10
```

## Configuration

All defaults live in `kadmon/config.py`:

```python
DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-6"
DEFAULT_PROVIDER = "bedrock"
DEFAULT_REGION = "us-east-1"
```

Update there when new models ship — CLI and eval pick it up automatically.

## Development

### Build & test loop

```bash
ruff check kadmon/ tests/    # Lint
pytest tests/ -v             # 61 tests
```

### Adding a new tool

1. Create `kadmon/tools/your_tool.py` extending `Tool`
2. Define `name`, `description`, `parameters` (JSON Schema), `execute()`
3. Register in `kadmon/tools/__init__.py` → `create_default_registry()`
4. Add tests, run `./dev test && ./dev lint`

### Commit convention

[Conventional Commits](https://www.conventionalcommits.org/) with scopes:

```
feat(tools): add rename_symbol tool
fix(agent): prevent infinite loop on repeated edit failures
test(eval): add polyglot benchmark edge cases
```

See [AGENTS.md](AGENTS.md) for full AI contribution guidelines.

## CLI Reference

```
kadmon run       Run the agent on a task
kadmon bench     Run Aider Polyglot benchmark
kadmon eval      Run SWE-bench evaluation

Defaults (from kadmon/config.py):
  model:     us.anthropic.claude-sonnet-4-6
  provider:  bedrock
  region:    us-east-1

kadmon run:
  --task          Task description (required)
  --repo          Repository path (default: .)
  --model         Override model
  --provider      anthropic | bedrock
  --aws-region    Override region

kadmon bench:
  --languages     Comma-separated: python,javascript,go,rust,java,cpp
  --limit         Max exercises
  --output        Output directory
  -j, --workers   Parallel workers (default: 4)
  --setup/--no-setup  Clone exercism repos if needed

kadmon eval:
  --dataset       Path to SWE-bench instances JSON
  --limit         Max instances
  --output        Output directory
```

## License

MIT
