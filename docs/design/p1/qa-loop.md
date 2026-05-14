# Intelligent Verification

## Overview

Kadmon verifies like a senior dev, not like a CI pipeline. It understands the project's verification landscape, chooses the right level of verification for the moment, and proactively fills testing gaps — or asks when new infrastructure is needed.

The promise: a human reviewing Kadmon's work should never think "did you even test this?"

## The Problem

Agents today either:
- Run nothing (hope for the best, ship broken code)
- Run everything after every edit (slow, wasteful, still misses real issues)
- Write fake unit tests that test the implementation, not the behavior

None of these earn trust. Trust comes from intelligent verification — the same judgment a senior engineer applies.

## What a Senior Dev Does

| Moment | Action | Speed |
|--------|--------|-------|
| During development | Run the specific test for the code being changed | ~200ms |
| After a logical chunk | Run the module's test suite | ~2-15s |
| Before committing | Run full local suite + lint | ~30-60s |
| Before deploying | Integration/E2E tests | ~1-15min |

They also:
- Write a test FIRST when adding new behavior (locks in intent, not implementation)
- Notice when test coverage is missing and fill the gap
- Flag when verification requires infrastructure that doesn't exist

## Kadmon's Verification Model

### Phase 1: Learn the Verification Landscape

On first session, Kadmon discovers and stores in library:

```markdown
# Verification Profile
Scope: *

## Test Infrastructure
- Framework: pytest
- Unit tests: tests/unit/ (~2s full, ~200ms targeted)
- Integration tests: tests/integration/ (~15s, requires local DB)
- E2E: scripts/e2e.sh (~5min, requires deployed staging)
- Lint: ruff check src/
- Type check: mypy src/

## How to Run Targeted
- Single test: pytest tests/unit/test_auth.py::test_refresh -x
- Single file: pytest tests/unit/test_auth.py
- Module: pytest tests/unit/auth/

## Gaps
- No integration tests for payment module
- E2E only covers happy path
```

This is a library entry (path-scoped to `*` = global). Updated by the Curator when the agent discovers new test infrastructure.

### Phase 2: Choose Verification by Moment

The agent decides what to verify based on context:

| Situation | Verification choice |
|-----------|-------------------|
| Fixed a typo in one function | Run that function's test |
| Implemented a new feature (plan step done) | Run module tests |
| All plan steps complete, about to submit | Full suite + lint |
| Changed behavior that has E2E coverage | Run E2E at the end |
| No tests exist for this code | Write one first (see Phase 3) |

This is NOT a mechanical hook. It's prompt-guided judgment with a mechanical backstop.

### Phase 3: Proactive Gap-Filling

Kadmon holds an opinion on what "well-verified" means:

1. **At least one test that would fail if the change broke** (behavior test, not implementation test)
2. **Regression coverage** (existing tests still pass)
3. **Appropriate scope** (unit for logic, integration for interactions, E2E for flows)

Three postures based on what's missing:

**Execute mechanically** (just do it):
- Tests exist → run them
- New function needs a unit test → write it
- Existing test needs updating for new behavior → update it
- Test file exists but doesn't cover the changed code path → add a case

**Stop and ask** (ask_human — new paradigm/infra needed):
- "This service has no integration tests. I think we need a test harness with a local DB. Should I build that, or is there an existing pattern?"
- "There's no way to verify this locally — it requires a deployed environment. Do you have staging, or should I build a local mock?"
- "The existing tests all mock the database. They won't catch this bug class. OK to add a real integration test with a test DB dependency?"
- "I'd like to add E2E tests but there's no test runner for the frontend. Should I set up Playwright/Cypress?"

**Flag and proceed** (inform, don't block):
- "Verified with unit tests. No E2E coverage for this flow — flagging for manual verification."
- "Tests pass but this module has low coverage. Consider adding integration tests."

### Phase 4: Mechanical Backstop

Regardless of the agent's judgment, the system enforces:

- **Before submit**: at least one test run must have passed this session (any level)
- **After failed edit**: if the agent edits a file and the targeted test fails, it MUST fix or rollback before proceeding (uses existing checkpoint system)
- **Max retries**: 3 attempts to fix a failing test, then rollback + ask_human with full context of what was tried

## Implementation

### VerificationProfile (stored in library)

Discovered on first session, updated by Curator. Contains:
- Available test commands + approximate timings
- How to run targeted tests (per-file, per-function patterns)
- Known gaps (modules without tests, missing infrastructure)

### QARunner (`kadmon/qa.py`)

```python
@dataclass
class QAResult:
    passed: bool
    output: str
    duration: float
    command: str

class QARunner:
    def __init__(self, repo_root: str): ...
    def discover(self) -> VerificationProfile: ...
    def run_targeted(self, file: str) -> QAResult: ...
    def run_module(self, path: str) -> QAResult: ...
    def run_full(self) -> QAResult: ...
    def run_lint(self) -> QAResult: ...
```

### Agent Integration

NOT a mechanical hook after every edit. Instead:

1. **Prompt guidance** — EDITOR_PROMPT tells the agent about the verification landscape and when to verify
2. **Verification tool** — `verify` tool the agent calls explicitly (wraps QARunner)
3. **Submit gate** — submit tool checks that at least one verification passed this session
4. **Retry injection** — when verification fails, output is injected into context automatically

### Prompt additions (EDITOR_PROMPT)

```
## Verification
You have a `verify` tool. Use it intelligently:
- After editing implementation: verify(target="path/to/test_file.py") for fast feedback
- After completing a plan step: verify(scope="module") for regression check  
- Before submitting: verify(scope="full") for confidence

If no tests exist for the code you're changing:
- If you can write a behavior test mechanically: write it, then implement
- If testing requires new infrastructure: ask_human before proceeding

Never submit without at least one passing verification run.
```

## What This Is NOT

- Not TDD dogma (agent chooses when test-first is appropriate)
- Not "run pytest after every line" (agent chooses verification level)
- Not a CI replacement (this is local dev-loop verification)
- Not mandatory for every project (graceful fallback if no tests exist)

## Open Questions

1. Should the `verify` tool have a timeout? (Probably yes — 60s default, configurable)
2. Should verification profile discovery be its own agent (like IndexAgent) or simpler heuristic-based?
3. How does the agent learn timings? (Run once, measure, store in profile)

## Success Criteria

1. Agent never submits code without having verified it at some level
2. Agent writes tests for new behavior proactively (not just running existing tests)
3. Agent asks_human when verification infrastructure is missing (not silently shipping untested code)
4. Agent chooses appropriate verification level (not running E2E after a one-line fix)
5. Human reviewing Kadmon's output feels confident it was tested properly
