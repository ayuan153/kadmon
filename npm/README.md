# kadmon

An autonomous coding agent that manages its own context across sessions.

## Install

```bash
npm install -g kadmon
```

Requires Python 3.11+ (the npm package auto-installs the Python backend on first run).

## Usage

```bash
# Interactive setup
kadmon init

# Run on a repo
cd your-project
kadmon run --task "Fix the failing test in test_auth.py"

# Benchmark
kadmon bench --languages python --limit 5
```

## What is this?

This npm package is a thin wrapper around the [kadmon Python package](https://github.com/ayuan153/kadmon). It:

1. Checks for Python 3.11+
2. Installs the `kadmon` pip package if not present
3. Forwards all commands to the Python CLI

For full documentation, see the [GitHub repo](https://github.com/ayuan153/kadmon).
