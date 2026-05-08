# Kadmon: Autonomous Context Management — Implementation Plan

## Vision

Kadmon should behave like a senior engineer managing their own work — not a tool that needs babysitting. The human's role is that of a business leader: set direction, answer questions, approve decisions. The agent handles everything else, including managing its own cognitive lifecycle.

### Three Pillars

1. **No guessing** — Surface ambiguity to the human, get answers, then execute with confidence
2. **Rock climbing** — Verify each step before moving to the next (feedback loops over speculation)
3. **Self-managing context** — When context gets stale or the task pivots, autonomously write a handoff and continue in a fresh session

### Key Innovation

The agent detects when it should "cut itself off" — writes structured memory to the library, crafts a continuation prompt, and hands off to a fresh zero-context session. The human doesn't manage this.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    KADMON ORCHESTRATOR                        │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Handoff  │  │ Question │  │  Worker  │  │  Pruner   │  │
│  │ Monitor  │  │  Batcher │  │ Subagent │  │ Subagent  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       │              │             │               │         │
│  ┌────┴──────────────┴─────────────┴───────────────┴─────┐  │
│  │                    LIBRARIAN                            │  │
│  │         (file-based memory library)                    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              HUMAN INTERFACE                            │  │
│  │    (CLI block + Slack/webhook push + async continue)   │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Subagent Roles

| Subagent | Role | When Active |
|----------|------|-------------|
| **Worker** | Does the actual coding/research | Always (this is the current agent loop) |
| **Librarian** | Reads/writes the file-based memory library | On session start, on handoff, on explicit save |
| **Pruner** | Strips irrelevant context when task pivots | On task boundary detection, on handoff |
| **Handoff Monitor** | Detects when context is degrading or task is pivoting | Continuously (lightweight check after each step) |
| **Question Batcher** | Collects open questions, batches them for human | When ambiguity detected |

---

## Phase 4a: Librarian + File-Based Memory Library

**Goal:** Persistent, structured knowledge that outlives sessions.

### Library Structure

```
.kadmon/
├── config.toml              # Project config (existing)
├── symbols.db               # Symbol index (existing)
├── library/
│   ├── index.md             # Table of contents (auto-maintained)
│   ├── architecture.md      # Project architecture notes
│   ├── decisions.md         # Key decisions and rationale
│   ├── conventions.md       # Code style, patterns, gotchas
│   └── tasks/
│       ├── current.md       # Active task context
│       └── completed/
│           ├── fix-auth-bug.md
│           └── add-pagination.md
└── handoffs/
    ├── latest.md            # Most recent handoff doc
    └── history/
        └── 2026-05-08T10-00.md
```

### Library Operations

```python
class Librarian:
    """Manages the file-based memory library."""
    
    def load_relevant(self, task: str) -> str:
        """Load library entries relevant to the current task."""
    
    def save_learning(self, category: str, content: str):
        """Save a new learning to the appropriate library file."""
    
    def save_task_context(self, task: str, context: str):
        """Save current task state for potential handoff."""
    
    def get_cold_start_context(self) -> str:
        """Build context for a fresh session from library."""
```

### Scope
- Per-repo library (`.kadmon/library/`)
- Markdown files (human-readable, git-friendly)
- Librarian decides what to load based on current task (keyword match initially, embeddings later)
- Auto-maintains `index.md` as table of contents

### Tasks
- [ ] Library directory structure and file format spec
- [ ] Librarian class: load_relevant, save_learning, save_task_context
- [ ] Cold start: on session begin, load config + relevant library entries
- [ ] Auto-save: after completing a plan step, save learnings
- [ ] Index maintenance: update index.md when library changes

---

## Phase 4b: Human-in-the-Loop (Question Batching)

**Goal:** Agent surfaces ambiguity as batched questions, blocks until answered, continues non-blocked work in parallel.

### Behavior

1. Agent detects ambiguity (multiple valid interpretations, missing info, risky decision)
2. Collects questions into a batch (max 3-5 per batch)
3. Pushes batch to human via configured channel (CLI prompt, Slack webhook, etc.)
4. Blocks the ambiguous work path
5. Continues any independent work that doesn't depend on the answers
6. When answers arrive, incorporates them and resumes

### Question Categories

| Category | Trigger | Example |
|----------|---------|---------|
| Ambiguous requirement | Multiple valid interpretations | "Should /users return 404 or empty list?" |
| Architecture decision | Multiple valid approaches | "Add as middleware or decorator?" |
| Missing information | Can't infer from code | "What's the expected timeout?" |
| Risk confirmation | Destructive or irreversible action | "This deletes the users table. Proceed?" |

### Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `yolo` | Never ask, make best judgment | Benchmarking, trusted autonomous work |
| `cautious` (default) | Ask on ambiguity, batch questions | Normal development |
| `paranoid` | Ask before any non-trivial action | Critical systems, learning phase |

### Channel Abstraction

```python
class HumanChannel(Protocol):
    def ask(self, questions: list[Question]) -> list[Answer]: ...
    def notify(self, message: str): ...

class CLIChannel: ...      # input() with rich formatting
class SlackChannel: ...    # Post to channel, poll for reply
class WebhookChannel: ...  # POST questions, poll for response
```

### Tasks
- [ ] Question dataclass (category, context, options if applicable)
- [ ] QuestionBatcher: collects questions, triggers when batch ready
- [ ] CLIChannel implementation (block + wait with timeout)
- [ ] Webhook/Slack channel (push notification + poll)
- [ ] Integration with agent loop: detect ambiguity → batch → ask → resume
- [ ] `--mode yolo/cautious/paranoid` CLI flag
- [ ] Non-blocked work continuation (identify independent plan steps)

---

## Phase 4c: Autonomous Handoff

**Goal:** Agent detects when it should hand off to a fresh session and does so without human intervention.

### Handoff Triggers

The Handoff Monitor checks after each plan step:

| Trigger | Detection Method |
|---------|-----------------|
| **Token budget** | Context utilization > 80% |
| **Task boundary** | Current plan complete, new task starting |
| **Quality degradation** | Loop detector firing frequently, edits getting reverted |
| **Explicit pivot** | Human says "now do X" (unrelated to current task) |

### Handoff Process

```
1. DETECT: Handoff Monitor fires
2. SAVE: Librarian saves current task state + learnings
3. PRUNE: Pruner identifies what's relevant for continuation
4. CRAFT: Generate handoff document:
   - What was accomplished
   - What's in progress
   - What's next (remaining plan steps)
   - Key context the fresh session needs
   - Relevant library entries to load
5. RESET: Clear message history
6. RESUME: Load handoff doc as initial context, continue
```

### Handoff Document Format

```markdown
# Handoff — 2026-05-08T10:00:00

## Accomplished
- Fixed auth bug in UserService (PR #42 open)
- Added input validation to /users endpoint

## In Progress
- Step 3 of plan: Add rate limiting middleware

## Remaining Plan
- [ ] Add rate limiting middleware to /api routes
- [ ] Write integration tests for rate limiting
- [ ] Update API documentation

## Key Context
- Project uses Express.js with TypeScript
- Rate limiting should use redis (already in deps)
- Tests use jest + supertest

## Load from Library
- .kadmon/library/architecture.md
- .kadmon/library/conventions.md
```

### Same-Process Handoff (default)

```python
class HandoffManager:
    def execute_handoff(self, agent_loop: AgentLoop):
        """Clear context and resume from handoff doc."""
        # 1. Save state
        self.librarian.save_task_context(...)
        handoff_doc = self.craft_handoff(agent_loop)
        
        # 2. Write handoff file
        self.save_handoff(handoff_doc)
        
        # 3. Clear context (same process, fresh messages)
        agent_loop.context = ContextManager()
        
        # 4. Load handoff as new starting context
        cold_start = self.librarian.get_cold_start_context()
        agent_loop.context.add(Message(role='user', content=cold_start + handoff_doc))
        
        # 5. Continue (loop resumes naturally)
```

### Tasks
- [ ] HandoffMonitor: checks triggers after each plan step
- [ ] Handoff document generation (structured markdown)
- [ ] HandoffManager: orchestrates save → prune → craft → reset → resume
- [ ] Same-process handoff (clear context, reload from handoff)
- [ ] CLI invocation handoff (for cross-repo or explicit restart)
- [ ] Handoff history (`.kadmon/handoffs/history/`)
- [ ] Configurable triggers (which ones are active, thresholds)

---

## Phase 4d: Pruner Subagent

**Goal:** When task pivots or handoff occurs, strip irrelevant context to keep the fresh session focused.

### What Gets Pruned

| Keep | Prune |
|------|-------|
| Current task description | Old task exploration results |
| Relevant library entries | Stale file reads from old task |
| Active plan steps | Completed/failed plan steps (summarize only) |
| Key decisions made | Verbose tool outputs |
| Error patterns learned | Successful tool outputs (already in code) |

### Pruner Operations

```python
class Pruner:
    def prune_for_handoff(self, context: ContextManager, new_task: str) -> str:
        """Extract only what's relevant for the new task."""
    
    def prune_library(self, library_path: Path, current_task: str):
        """Archive old task entries, keep relevant ones active."""
    
    def summarize_completed_work(self, plan: Plan) -> str:
        """One-paragraph summary of what was done (not how)."""
```

### Tasks
- [ ] Pruner class with prune_for_handoff, prune_library, summarize_completed_work
- [ ] Relevance scoring (keyword overlap between context and new task)
- [ ] Library archival (move completed task docs to `completed/`)
- [ ] Integration with HandoffManager (prune before crafting handoff doc)

---

## Phase 4e: Steering & Configuration

**Goal:** Make the autonomous behavior configurable and observable.

### `.kadmon/config.toml` Extensions

```toml
[agent]
mode = "cautious"  # yolo | cautious | paranoid
auto_handoff = true
handoff_threshold = 0.8  # context utilization trigger
max_questions_per_batch = 5
question_timeout = 300  # seconds before proceeding with best guess

[channels]
primary = "cli"  # cli | slack | webhook
slack_webhook = ""
slack_channel = ""

[library]
auto_save = true
max_entries = 100
prune_after_days = 30
```

### Observability

- Log handoff events to `.kadmon/handoffs/history/`
- Log questions asked + answers received
- Track: sessions per task, handoffs per session, questions per task
- `kadmon status` command: show library size, last handoff, active task

### Tasks
- [ ] Config extensions (mode, channels, thresholds)
- [ ] `kadmon status` command
- [ ] Handoff event logging
- [ ] Question/answer logging

---

## Implementation Order

```
Phase 4a (Week 1-2): Librarian + Library
    ↓
Phase 4b (Week 3-4): Human-in-the-Loop
    ↓
Phase 4c (Week 5-6): Autonomous Handoff
    ↓
Phase 4d (Week 7): Pruner
    ↓
Phase 4e (Week 8): Steering + Config + Observability
```

Each phase is independently useful:
- 4a alone: agent remembers across sessions
- 4a+4b: agent asks good questions and remembers answers
- 4a+4b+4c: agent manages its own context lifecycle
- 4a+4b+4c+4d: agent stays focused when tasks change

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Library format | Markdown files | Human-readable, git-friendly, no DB dependency |
| Library scope | Per-repo (`.kadmon/library/`) | Different repos have different context |
| Handoff mechanism | Same-process (clear context) | Fast, no cold start, shared index/tools |
| Session persistence | Not OMKC-compatible | Different needs (library vs delegation tracking). Migration trivial if needed later. |
| Question delivery | Batch + block | Fewer interruptions, human can answer in one go |
| Pruning approach | Subagent (LLM-based relevance) | Rule-based pruning misses semantic relevance |
| Compaction | Replaced by handoff | Compaction loses info; handoff preserves it in library |
| Mode system | yolo/cautious/paranoid | Benchmarks need yolo, daily work needs cautious |

---

## Relationship to Benchmarking

The autonomous features are **disabled in benchmark mode** (`--mode yolo`):
- No questions asked
- No handoffs (single-shot execution)
- No library writes (each instance is independent)
- Pruner inactive

Benchmarking validates the **worker** (coding ability). Autonomous features validate the **experience** (working with kadmon daily). Both matter, but they're tested differently.

---

## Success Criteria

**Phase 4 is done when:**
1. Kadmon can work on a multi-day task across 5+ sessions without human context management
2. A fresh session picks up exactly where the last one left off (from handoff doc)
3. The agent asks ≤5 focused questions per task (not 0, not 20)
4. Context never degrades — handoff fires before quality drops
5. Library accumulates useful knowledge that measurably helps future sessions
6. A human can `cat .kadmon/library/` and understand the project's state

**The ultimate test:** Give kadmon a 3-sentence task description for a feature that takes 2 days of work. Come back in 2 days. The feature is done, the PR is open, and the library documents what was built and why.
