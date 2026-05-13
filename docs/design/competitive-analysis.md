# Competitive Analysis & Feature Roadmap

Research into OMKC (Oh-my-kiro-cli), Cline, OpenAI Codex, and Claude Code — what to steal, what to skip, and what to innovate on.

## Kadmon's Differentiators (Non-Negotiable)

1. **Autonomous context management** — detects degradation, writes its own handoff, resets, continues. No other agent does this natively.
2. **YOLO you can trust** — full autonomy on tool use and execution, but asks liberally for direction, grounding, and implementation decisions. The trust comes from speaking up, not from skipping checks.
3. **Self-managing library** — agent writes its own persistent memory (not user-maintained like CLAUDE.md or Memory Bank).
4. **Mechanical + intelligent persistence** — deterministic capture (flight recorder) + LLM curation (librarian). Belt and suspenders.
5. **Heavy QA emphasis** — fast, deterministic, high-coverage feedback loops. Autonomy without verification is just gambling.

## Features to Implement (Table Stakes)

| Feature | From | Kadmon Adaptation |
|---------|------|-------------------|
| Checkpoints (shadow git) | Cline | Snapshot working tree before edits. Enable rollback without touching user's git history. |
| AGENTS.md support | Codex/Claude Code | Read on cold start, merge into library. Cross-tool standard. |
| Parallel subagents | Codex/OMKC/Cline | Fan out independent subtasks to separate context windows. Merge results. |
| Path-scoped rules | Claude Code | Library entries tagged with file paths; loaded only when those paths are relevant. |

## Features to Skip

| Feature | From | Why Skip |
|---------|------|----------|
| User-maintained memory files | Cline (Memory Bank) | Kadmon's library is self-managing. Don't regress to requiring user curation. |
| Cloud sandboxes | Codex | Kadmon is local-first, no phone-home. |
| Compaction/summarization | Claude Code/Cline | Ineffective. Kadmon's approach: targeted handoff prompt + pointers for next task, with minimal background context the agent can retrieve as needed. Fresh context > degraded summary. |
| Rigid delegation templates | OMKC | Over-structured for a single-agent system. |
| "Minimize clarifying questions" | Claude Code (auto mode) | Directly opposes Kadmon's core value. |
| Visible plan as static checklist | Cline (Focus Chain) | Plans need to be flexible and evolve. A rigid visible checklist is an overoptimization that constrains adaptation. |

## The YOLO Reframe

Other agents treat YOLO as "skip all safety checks." Kadmon reframes it:

**Kadmon's YOLO = full autonomy on execution + liberal ask_human for direction.**

| Dimension | Other Agents' YOLO | Kadmon's YOLO |
|-----------|-------------------|---------------|
| Tool use | Auto-approve everything | Auto-approve everything |
| File edits | No confirmation | No confirmation |
| Shell commands | No confirmation | No confirmation |
| Ambiguous requirements | Guess and go | **ask_human** |
| Design decisions | Pick one silently | **ask_human** |
| Uncertain about approach | Try something | **ask_human** |
| After implementation | Move on | **Run tests, verify, QA loop** |

The insight: users don't want to approve `mkdir` and `git add`. They want to approve *decisions*. Kadmon auto-executes mechanics but escalates judgment calls.

## Features to Innovate On

| Innovation | Kadmon's Approach |
|-----------|-------------------|
| **Targeted handoff (not compaction)** | On context degradation: write a focused prompt + pointers to relevant docs/code. Clear context to 0 (or near-0). Fresh start with surgical context > bloated summary. |
| **Confidence-gated asking** | No user-configured modes. Agent self-assesses per action: high confidence on mechanics → act. Uncertainty on direction/design → ask. |
| **Cross-session task continuity** | Central index + structured handoffs + library = seamless multi-session work without user managing state. |
| **QA-first autonomy** | Every change verified by fast feedback loops (tests, type checks, lints). Autonomy is earned by proving correctness, not by skipping verification. |
| **Proactive handoff** | Detect degradation + write handoff + reset + continue. No other agent does this. |

## Priority Roadmap

### P0 — Ship Next

1. **Checkpoints (shadow git)** — Snapshot before edits, rollback on failure or request.
2. **AGENTS.md support** — Read on cold start, merge into library context.
3. **Path-scoped library entries** — Tag entries with file paths, load only when relevant.
4. **Parallel workers** — Fan out independent subtasks to separate context windows.

### P1 — Build Soon

5. **Confidence-gated actions** — Self-assess before each action. Mechanics → act. Judgment → ask.
6. **QA loop integration** — Auto-run tests/lint after every edit. Fail → fix → retry loop before moving on.
7. **Targeted handoff refinement** — Improve handoff doc quality: focused prompt, minimal pointers, clear next-step.

### P2 — Build Later

8. **Model routing** — Cheap model for indexing/planning, strong model for editing/synthesis.
9. **Hooks API** — User-defined pre/post hooks on tool calls for custom automation.
10. **Auto-review on risky actions** — Second LLM pass on destructive commands before executing.

## Philosophical Stance

Kadmon is the agent you trust to run unsupervised — not because it never asks questions, but because it asks the RIGHT questions and proves its work.

- **Claude Code** optimizes for speed (auto mode, minimize questions)
- **Codex** optimizes for safety (sandboxes, platform enforcement)
- **Cline** optimizes for control (checkpoints, granular approvals)
- **Kadmon** optimizes for TRUST (ask when uncertain, prove when done, remember across sessions)

The bet: YOLO-with-judgment beats YOLO-with-silence. Developers will give unlimited autonomy to an agent that asks "should this be a REST endpoint or a GraphQL resolver?" before building the wrong thing — and then proves it works with passing tests.

## Features to Steal

| Feature | From | Why | Adaptation for Kadmon |
|---------|------|-----|----------------------|
| Checkpoints (shadow git) | Cline | Fearless rollback mid-task without touching user's git | Snapshot before each edit; rollback on failure or user request |
| Plan/Act mode with model routing | Cline | Use cheap model for planning, strong model for execution | Already have architect/editor split; add model routing |
| Path-scoped rules | Claude Code | Load instructions only when relevant files are touched | Extend library with path-triggered context |
| AGENTS.md support | Codex/Claude Code | Becoming a cross-tool standard; read it on cold start | Read AGENTS.md into library on first session |
| Focus Chain (visible todo) | Cline | Users want to SEE progress, not just trust the agent | Surface plan steps as a persistent visible checklist |
| Auto-review agent | Codex | Reduce human interruption without going YOLO | Second LLM pass on risky actions; cheaper than asking human |
| Hooks system | OMKC/Cline/Codex | Lifecycle extensibility without forking | Pre/post tool-call hooks (already partially built via session logger) |
| Compaction that re-reads persistent docs | Claude Code | Ensures AGENTS.md/library survives summarization | After compaction, re-inject library context via library_read |
| Parallel subagents | Codex/OMKC/Cline | Fan out independent research/implementation | Add worker spawning for independent subtasks |

## Features to Skip (Conflicts with Vision)

| Feature | From | Why Skip |
|---------|------|----------|
| YOLO/blanket auto-approve | Cline/Codex | Conflicts with ask-for-correctness. Kadmon's trust comes from ASKING, not from skipping checks. |
| User-maintained memory files | Cline (Memory Bank) | Kadmon's library is self-managing. Don't regress to requiring user curation. |
| Cloud sandboxes | Codex | Kadmon is local-first, no phone-home. Sandbox locally if needed. |
| Rigid delegation templates | OMKC | 7-section protocol is over-structured for a single-agent system. Kadmon delegates to itself (architect→editor), not to 13 subagents. |
| "Never say I can't" | OMKC | Kadmon SHOULD say "I'm not sure" — that's the ask-human philosophy. Honesty > bravado. |
| Minimize clarifying questions | Claude Code (auto mode) | Directly opposes Kadmon's core value. We ask MORE, not less. |
| Token-count-only compaction trigger | Cline | Kadmon already detects quality degradation (loops, repeated errors). Don't downgrade to just "context full." |

## Features to Innovate On

| Innovation | Inspiration | Kadmon's Twist |
|-----------|-------------|----------------|
| **Proactive handoff** | None do this | Kadmon detects degradation AND writes structured handoff AND resets AND continues. Unique. |
| **Confidence-gated autonomy** | Codex auto-review | Instead of permission tiers, Kadmon self-assesses confidence per action. High confidence → act. Low confidence → ask. No user-configured modes. |
| **Mechanical + curated memory** | OMKC hooks + Claude Code memory | Deterministic capture (never lose data) + LLM synthesis (keep it useful). Neither alone is sufficient. |
| **Ask-human as a TOOL, not a mode** | All agents have modes | Kadmon's ask_human is always available regardless of "mode." It's a tool the agent uses when uncertain, not a permission gate the user configures. |
| **Cross-session task continuity** | None do this well | Central index + structured handoffs + library = seamless multi-session work without user managing state. |
| **Grounded planning** | Cline plan mode | Kadmon's architect phase should VERIFY assumptions (run tests, read code) before planning, not just think. Rock climbing = verify each hold. |

## Priority Roadmap

### P0 — Ship Next (High Impact, Aligned with Vision)

1. **AGENTS.md support** — Read on cold start, merge into library. Low effort, high compatibility.
2. **Visible plan progress** — Surface the plan tool's state as a persistent checklist the user can see. Already have the data; need the UX.
3. **Compaction → re-read library** — After context compaction, call library_read to restore persistent knowledge. Prevents amnesia.

### P1 — Build Soon (Differentiating)

4. **Confidence-gated actions** — Agent self-assesses before each action. Replace binary ask/don't-ask with a confidence score. High → act silently. Medium → mention what you're doing. Low → ask_human.
5. **Checkpoints (shadow git)** — Snapshot working tree before edits. Enable rollback without touching user's git history.
6. **Parallel workers** — Fan out independent subtasks to separate context windows. Merge results.

### P2 — Build Later (Polish)

7. **Model routing** — Cheap model for planning/indexing, strong model for editing/synthesis. Cost optimization.
8. **Path-scoped library entries** — Library entries tagged with file paths; only loaded when those paths are relevant.
9. **Hooks API** — User-defined pre/post hooks on tool calls for custom automation.
10. **Auto-review on risky actions** — Second LLM pass on destructive commands (rm -rf, force push, etc.) before executing.

## Philosophical Stance

Kadmon is NOT trying to be the fastest or most autonomous in the "never asks questions" sense. It's trying to be the most TRUSTWORTHY autonomous agent:

- **Claude Code** optimizes for speed (auto mode, minimize questions)
- **Codex** optimizes for safety (sandboxes, platform enforcement)
- **Cline** optimizes for control (checkpoints, granular approvals)
- **Kadmon** optimizes for TRUST (ask when uncertain, prove when done, remember across sessions)

The bet: developers will give MORE autonomy to an agent they trust to ask good questions than to one that just plows ahead. Trust compounds. Speed without trust leads to "undo, redo, undo" loops that waste more time than asking would have.
