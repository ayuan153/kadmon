# QA Loop: Mechanical Verification After Every Edit

## Overview

Currently, test-after-edit is prompt-dependent — the LLM might forget, skip, or not know the command. The QA Loop makes verification **mechanical**: the system automatically runs tests after every file write, injecting failures back into context for the agent to fix. This is how "YOLO you can trust" works — autonomy earned through proven correctness.

## What "QA" Means Here

- **Fast feedback only**: lint, type check, unit tests — things that complete in seconds
- **NOT**: manual testing, integration tests, deployment, E2E suites
- Goal: tight `edit → verify` loop, not comprehensive QA

## How It Works

1. Agent calls `edit_file` or `write_file` → tool succeeds
2. System automatically runs the configured verification command
3. **Pass** → continue normally
4. **Fail** → inject failure output into context, agent gets a turn to fix
5. **Fail 3 times** → `checkpoint_rollback` → `ask_human` with summary of attempts

## Verification Command Discovery

1. `.kadmon/config.toml` → `[qa] command = "pytest -x"` (explicit)
2. Auto-detect: `package.json` scripts.test → `npm test` | `pyproject.toml` [tool.pytest] → `pytest` | `Makefile` test target → `make test` | `Cargo.toml` → `cargo test`
3. Agent sets it via tool call during exploration (stored in session state)
4. **Fallback**: no command found → skip verification, don't block

## Implementation

```python
@dataclass
class QAResult:
    passed: bool
    output: str  # stdout+stderr, truncated to 2000 chars
    duration: float

class QARunner:
    def discover_command(self, repo_root: Path) -> str | None: ...
    def run(self, repo_root: Path) -> QAResult: ...
```

**Hook point**: `AgentLoop._process_response()`, after successful `edit_file`/`write_file` — before returning control to the LLM.

**Config** (`.kadmon/config.toml`):
```toml
[qa]
enabled = true        # default true
command = "pytest -x" # optional, overrides auto-detect
timeout = 30          # seconds
max_retries = 3       # before rollback + escalation
```

## Retry Loop

```
edit_file("src/foo.py")
  → checkpoint exists (pre-edit, already implemented)
  → QA runs → FAIL (retry 1/3)
    → inject: "[QA FAILED] output: ..."
    → agent turn → fixes foo.py → QA runs → PASS → continue
    OR → FAIL (retry 2/3) → agent fixes → QA → PASS → continue
    OR → FAIL (retry 3/3) → checkpoint_rollback → ask_human
```

Each retry is a normal agent turn — it sees test output and decides how to fix.

## What NOT To Do

- Don't run QA after `read_file`, `grep`, `list_dir` — only after file writes
- Don't run QA if edited file matches `**/test_*` or `**/*_test.*` (avoid infinite loops)
- Don't run QA in architect mode — only editor mode
- Don't block on slow suites — kill after timeout, treat as skip
- Don't make QA mandatory — graceful no-op if no command discovered

## Checkpoint Interaction

Checkpoint is created BEFORE the edit (existing behavior). QA failure exhaustion → rollback to that checkpoint → file restored to pre-edit state. Agent never leaves files in a broken-tests state.

## Open Questions

1. Run after EVERY edit or only after plan-step completion? (Every edit = safer, slower)
2. Run relevant test file only or full suite? (Relevant = faster, might miss regressions)
3. Cache QA command per session or re-discover each time?

## Success Criteria

- Zero edits land with failing tests in final output (unless QA disabled/unavailable)
- Agent self-recovers from test failures without human intervention >80% of the time
- QA adds <2s overhead per edit for fast test suites
- No infinite loops from test-file edits triggering QA
