# Competitive Analysis & Feature Roadmap

Research into OMKC (Oh-my-kiro-cli), Cline, OpenAI Codex, and Claude Code — what to steal, what to skip, and what to innovate on.

## Kadmon's Differentiators (Non-Negotiable)

1. **Autonomous context management** — detects degradation, writes its own handoff, resets, continues. No other agent does this natively.
2. **Ask for correctness, not permission** — biases toward clarifying questions on ambiguity. Enables trust → enables autonomy.
3. **Self-managing library** — agent writes its own persistent memory (not user-maintained like CLAUDE.md or Memory Bank).
4. **Mechanical + intelligent persistence** — deterministic capture (flight recorder) + LLM curation (librarian). Belt and suspenders.

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
