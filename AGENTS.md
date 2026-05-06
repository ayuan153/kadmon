# AGENTS.md

Guidelines for AI agents contributing to this repository.

## Build & Test Loop

Every change must follow this cycle:

1. **Understand** — Read relevant code before modifying. Use `grep_search` or `find_symbols` to locate what you need. Never guess at file contents.
2. **Implement** — Make minimal, focused changes. One concern per edit.
3. **Lint** — Run `ruff check kadmon/ tests/` and fix any issues.
4. **Test** — Run `pytest tests/ -v`. All tests must pass. If you added new functionality, add tests for it.
5. **Commit** — Use conventional commits (see below). Only commit when lint + tests pass.

Do not skip steps. Do not commit broken code.

## Development Setup

```bash
pip install -e ".[dev]"
```

## Commands

| Task | Command |
|------|---------|
| Lint | `ruff check kadmon/ tests/` |
| Lint fix | `ruff check --fix kadmon/ tests/` |
| Test | `pytest tests/ -v` |
| Run agent | `kadmon run --task "..." --repo /path/to/repo` |
| Run eval | `kadmon eval --dataset instances.json --limit 10` |

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`

Scopes: `agent`, `tools`, `providers`, `eval`, `index`, `memory`, `cli`

Examples:
- `feat(tools): add grep_search with ripgrep fallback`
- `fix(agent): prevent infinite loop on repeated tool errors`
- `test(tools): add edit_file edge case coverage`
- `docs: update README with eval instructions`

Rules:
- One logical change per commit
- Implementation + its direct tests belong in the same commit
- Keep commits atomic — each should build and pass tests independently
- Never bundle unrelated changes

## Code Style

- Python 3.11+, type hints on all public functions
- Use `pathlib.Path` for filesystem operations
- Use dataclasses or pydantic models for structured data
- Keep functions short (<40 lines). Extract helpers.
- Error messages should be actionable (tell the user what to do next)
- No `# type: ignore`, no `Any` unless unavoidable

## Architecture Rules

- **Tools** are the agent's interface to the world. Optimize tool output for LLM consumption (concise, structured, actionable errors).
- **Providers** are stateless adapters. No business logic in providers.
- **Agent loop** is single-threaded ReAct. Keep it simple.
- **No frameworks** (no LangChain, no LangGraph). Use provider SDKs directly.
- All paths resolved relative to `repo_root`. Validate path escaping.

## Adding a New Tool

1. Create `kadmon/tools/your_tool.py` with a class extending `Tool`
2. Define `name`, `description`, `parameters` (JSON Schema)
3. Implement `execute(**kwargs) -> ToolResult`
4. Register in `kadmon/tools/__init__.py` inside `create_default_registry()`
5. Add tests in `tests/test_tools.py`
6. Run lint + tests before committing

## Adding a New Provider

1. Create `kadmon/providers/your_provider.py` implementing `LLMProvider` protocol
2. Handle message format conversion (internal ↔ provider-specific)
3. Add retry logic for transient errors
4. Register in provider factory
5. Add tests with mocked API responses

## File Structure

```
kadmon/
├── agent/       # Core loop, context management, planning
├── providers/   # LLM provider implementations
├── tools/       # Agent tools (file I/O, search, shell, etc.)
├── eval/        # SWE-bench evaluation harness
├── index/       # Tree-sitter symbol index (SQLite)
├── memory/      # Cross-session memory and handoff
└── cli.py       # CLI entry point
```

## What Not To Do

- Don't add dependencies without justification
- Don't add async unless the specific module requires it
- Don't modify the core loop without understanding the full message flow
- Don't delete or skip tests to make the build pass
- Don't leave debug prints or commented-out code
- Don't make changes outside the scope of your task
