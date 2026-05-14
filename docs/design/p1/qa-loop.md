# Intelligent Verification: Scout → Verify → Reflect

## Overview

Kadmon verifies like a senior dev. It understands the project's verification landscape (Scout), proves changes work at the appropriate level (Verify), and improves test quality after the fact (Reflect). The result: a human reviewing Kadmon's work never thinks "did you even test this?"

## The Three Phases

```
Scout (low frequency, cached in library)
  → "What does verification look like for this project?"

Build (the actual implementation work)

Verify (post-build, proportional to change)
  → "Prove this works — targeted tests, integration probes, new tests if needed"

Reflect (post-verify, non-trivial changes only)
  → "Can these tests be better? DRY, parameterized, high signal?"
```

---

## Phase 1: Scout

**When:** First session in a project, or when verification landscape changes.
**Frequency:** Low. Results cached in library as a VerificationProfile entry.
**Cost:** One exploration pass + library_write.

### What Scout discovers:

```markdown
# Verification Profile
Scope: *

## Test Infrastructure
- Framework: pytest
- Unit: tests/unit/ (~2s full, ~200ms targeted)
- Integration: tests/integration/ (~15s, requires local DB via docker-compose)
- E2E: scripts/e2e.sh (~5min, requires staging deploy)
- Lint: ruff check src/
- Type check: mypy src/

## How to Run Targeted
- Single test: pytest tests/unit/test_auth.py::test_refresh -x
- Single file: pytest tests/unit/test_auth.py
- Module: pytest tests/unit/auth/

## Shared Infrastructure
- conftest.py: db fixture, authenticated_client, factories
- tests/factories.py: UserFactory, PaymentFactory

## Gaps
- No integration tests for payment module
- E2E only covers happy path login flow
- No local way to test webhook handling

## Timings
- Unit (targeted): ~200ms
- Unit (full): ~2s
- Integration: ~15s
- E2E: ~5min
```

### When Scout re-runs:
- Agent discovers new test framework/tooling during work
- Agent notices a gap not previously recorded
- User changes test infrastructure (new conftest, new docker-compose, etc.)
- Curator updates profile from session log observations

---

## Phase 2: Verify

**When:** After building. Proportional to the change.
**Goal:** Prove the change works. Fast feedback during dev, broader checks before submit.

### Verification levels (agent chooses by moment):

| Moment | Action | Timing |
|--------|--------|--------|
| After editing implementation | Run targeted test for that code | ~200ms |
| After completing a plan step | Run module test suite | ~2-15s |
| New behavior with no existing test | Write a behavior test, then run it | ~30s |
| Before submit | Full suite + lint | ~30-60s |
| Non-trivial change to integration points | Run integration tests | ~15s-5min |

### Probing (the "manual test" equivalent):

When appropriate, the agent can:
- Run the application and hit it (curl, script, browser automation)
- Inspect output/logs to verify behavior
- **Then mechanize it** — turn the probe into an automated test

This is the natural flow: build → fastest check if it works → lock it in as a test.

The agent should prefer building reusable tooling (a test script, a fixture) over one-off manual probes when the pattern will recur.

### Three postures for missing tests:

**Execute mechanically** (just do it):
- New function needs a unit test → write it
- Existing test needs updating for new behavior → update it
- Can write a behavior test with existing fixtures → write it

**Stop and ask** (ask_human — new infra/paradigm needed):
- "No integration tests exist for this module. I'd need to set up a test DB. Should I?"
- "Can't verify this locally — needs a deployed environment. Do you have staging?"
- "Existing tests all mock the DB. They won't catch this bug class. OK to add real integration tests?"

**Flag and proceed** (inform, don't block):
- "Verified with unit tests. No E2E coverage for this flow — flagging for manual check."

### Mechanical backstop:

- Submit tool requires at least one passing test run this session
- If an edit breaks a targeted test: must fix or rollback before proceeding (max 3 retries, then rollback + ask_human)

---

## Phase 3: Reflect

**When:** After task is complete and verified. Skipped for trivial changes.
**Goal:** Improve test quality — DRY, parameterized, high signal, high recall.
**Key rule:** Refactoring existing tests the agent didn't write → ask_human first, separate commit.

### What Reflect evaluates:

1. **Duplication** — Are there tests covering the same behavioral path? → Parameterize
2. **Parameterization** — Could N similar tests be one parameterized test? → Refactor
3. **Signal** — Would these tests actually catch a regression? → Strengthen or remove
4. **Maintainability** — Are fixtures/factories reusable? → Extract shared infrastructure
5. **Coverage gaps** — Did we miss an important behavioral axis? → Flag or add

### Reflect workflow:

```
Agent completes task → runs Reflect analysis → identifies improvements →
  If improvements touch only tests written this session:
    → Apply them (same commit or amend)
  If improvements touch existing tests:
    → ask_human: "I noticed these existing tests could be improved: [description]. Want me to refactor? I'll put it in a separate commit."
    → If yes: refactor in separate commit on top
    → If no: note in library for future reference
```

### What "good tests" means (Kadmon's opinion):

- **Parameterized over duplicated** — one test with N cases, not N copy-pasted tests
- **Behavior over implementation** — test what the code does, not how it does it
- **Fixtures over setup repetition** — invest in test infrastructure early
- **Black-box surface area coverage** — identify input axes, cover the combinations
- **Strategic mocking** — mock slow/nondeterministic externals, test real logic

### Surface area mapping (pre-test-writing):

Before writing tests for a module, the agent maps:
```
This endpoint has 3 input axes:
  - Auth state: valid, expired, missing (3 values)
  - Request body: valid, malformed, empty (3 values)  
  - User role: admin, regular (2 values)
= 18 combinations. Recommend: 2 parameterized tests (happy + error paths)
  covering 18 cases, plus 1 edge-case test for the admin-only deletion flow.
```

---

## Implementation

### Components:

| Component | What it does |
|-----------|-------------|
| `VerificationProfile` | Library entry describing test landscape (Scout output) |
| `QARunner` (`kadmon/qa.py`) | Runs test commands, returns results with timing |
| `verify` tool | Agent calls explicitly with scope (targeted/module/full) |
| Submit gate | Blocks submit if no verification passed this session |
| Reflect prompt | Post-task analysis of test quality (prompt-guided, not mechanical) |

### QARunner interface:

```python
@dataclass
class QAResult:
    passed: bool
    output: str
    duration: float
    command: str

class QARunner:
    def __init__(self, repo_root: str): ...
    def discover(self) -> dict:  # Returns verification profile data
    def run_targeted(self, test_path: str) -> QAResult: ...
    def run_module(self, module_path: str) -> QAResult: ...
    def run_full(self) -> QAResult: ...
    def run_lint(self) -> QAResult: ...
    def run_command(self, command: str, timeout: int = 60) -> QAResult: ...
```

### Verify tool:

```python
class VerifyTool(Tool):
    name = "verify"
    description = "Run verification. Use after edits to prove changes work."
    parameters = {
        "scope": "targeted|module|full|lint|custom",
        "target": "path to test file or module (for targeted/module)",
        "command": "custom command to run (for custom scope)",
    }
```

### Prompt additions:

**EDITOR_PROMPT** — verification guidance:
```
## Verification
After edits, use `verify` to prove your changes work:
- verify(scope="targeted", target="tests/test_auth.py::test_refresh") — fast, after each edit
- verify(scope="module", target="tests/auth/") — after completing a plan step
- verify(scope="full") — before submitting
- verify(scope="custom", command="curl localhost:8000/health") — for integration probes

If no tests exist for the code you changed:
- Write a behavior test (parameterized if multiple cases) → then implement
- If testing requires new infrastructure → ask_human

Before submitting: at least one verification must have passed.
```

**Post-task Reflect** (injected after all plan steps complete):
```
Before submitting, review the tests you wrote or modified:
- Could any be parameterized instead of duplicated?
- Do they test behavior (what) or implementation (how)?
- Would they catch a real regression?
- Are there shared patterns that should be fixtures?
If existing tests need refactoring, ask_human before touching them.
```

---

## Success Criteria

1. Agent never submits without verification
2. Agent writes parameterized behavior tests, not bloated implementation tests
3. Agent proactively fills test gaps (mechanically when possible, asks when infra needed)
4. Agent identifies test quality improvements and proposes them (separate commit)
5. Test suites written by Kadmon are maintainable — a human reading them thinks "this is well-structured"
6. Agent respects test timings — doesn't run 5-minute E2E after a one-line fix
