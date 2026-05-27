# Handoff: Implement Workflow Discipline Prompts

## Background

Kadmon is an autonomous coding agent at `/Users/alleyuan/projects/kadmon`. We've built the full infrastructure (library team, session persistence, checkpoints, verification, parallel workers, confidence-gated prompts) and are now at the behavioral layer — making the agent follow a disciplined workflow by default.

Design doc: `docs/design/p1/workflow-discipline.md`

## What's Done

- All P0 features shipped (AGENTS.md, checkpoints/rewind, path-scoped rules, parallel workers)
- All P1 features shipped EXCEPT the workflow discipline prompt rewrites:
  - ✅ Intelligent Verification (Scout/Verify/Reflect) — `kadmon/qa.py`, `kadmon/tools/verify.py`
  - ✅ Confidence-Gated Actions — prompts have HIGH/MEDIUM/LOW framework
  - ✅ Handoff Refinement — `kadmon/memory/agents/handoff_agent.py`, LLM-synthesized briefs
- Persistent conversation in chat REPL (`continue_with()` method)
- Multi-language QA discovery (Python, JS, Go, Rust, Java, TypeScript)
- 230 tests passing, published at v0.6.0

## What's Next

**Implement the 5 workflow behaviors as prompt changes** (see `docs/design/p1/workflow-discipline.md`):

1. **Plan First** — ARCHITECT_PROMPT should make doc-writing the default for nontrivial tasks (design implications or multi-file)
2. **Surface Open Questions Continuously** — SYSTEM_PROMPT: "If you have open questions, surface them at the end of your response. Don't wait."
3. **Test Failure Decision Tree** — EDITOR_PROMPT: add the decision tree from `aa2/AGENTS.md` (test asserts correct behavior → fix code; test is wrong → fix test; NEVER weaken assertions)
4. **Reflect & Document** — EDITOR_PROMPT post-completion: update docs/README if relevant
5. **Auto-Detect Handoff Points** — extend `HandoffMonitor` with "clean break" heuristic (plan complete + next work is in different area → offer handoff)

Then: **Session resumption** — on startup, check for recent handoff, present summary if user prompt is low-detail, start fresh if high-detail.

## Key Files

- `kadmon/agent/prompts.py` — all three prompts to rewrite
- `kadmon/agent/handoff.py` — HandoffMonitor to extend with clean-break detection
- `kadmon/agent/loop.py` — startup logic for session resumption
- `docs/design/p1/workflow-discipline.md` — the full behavioral spec

## How to Verify

```bash
./dev test    # 230 tests should pass
./dev lint    # ruff check
./dev         # interactive test — try "tell me about yourself" (should respond conversationally, no tools)
              # try a vague prompt (should ask questions)
              # try a specific task (should plan first if nontrivial)
```
