# Handoff Refinement

## Overview

**Problem:** Current handoff dumps raw plan state into a verbose doc, injects cold-start context blobs on resume, and produces a generic "continue from where you left off" prompt. Result: degraded context replaced by bloated context.

**Goal:** Handoff produces a ~20-30 line task brief — like a senior dev writing a ticket for a colleague taking over. Fresh context retrieves background on demand, not upfront.

## Handoff Doc Format

```markdown
# Task: [one-line goal]

## What's Done
- [completed step — with file paths]

## What's Next
- [specific next action with file path and what to do]

## Key Context
- [pointer: "Auth logic is in src/auth/refresh.py, see validate_token"]
- [decision: "We chose JWT over sessions for horizontal scaling"]

## How to Verify
- [test command that proves correctness]
```

## Generating the Handoff

Replace mechanical plan-dump with a single LLM call (HandoffAgent) that synthesizes from:
- Current plan state (done/pending steps)
- Session log (files touched, tools used)
- Recent context (last few tool results)

The LLM compresses these inputs into the focused format above.

**HandoffAgent system prompt:**
```
You are writing a task handoff for another agent taking over this work.
Write a focused task brief (not a full history). Include:
- One-line goal
- What's already done (with file paths)
- What to do next (specific, actionable)
- Key context pointers (files, decisions, gotchas)
- How to verify the work
Keep it under 30 lines. Be specific — file paths, function names, test commands.
```

## Resume Flow

1. Fresh context starts with ONLY the handoff doc as the user message
2. Agent calls `library_read` if it needs background (on-demand)
3. Agent calls `verify(scope="discover")` if it needs test infrastructure info
4. No blob injection. No `librarian.get_cold_start_context()`

## Integration

| System | Role |
|--------|------|
| Session log | "What happened" — mechanical, complete |
| Handoff doc | Task brief for next session — focused, actionable |
| Curator | Runs AFTER handoff, synthesizes learnings into library |
| Library | Background knowledge — retrieved on demand via `library_read` |

## Implementation

1. **New:** `kadmon/memory/agents/handoff_agent.py` — LLM call to synthesize handoff from plan + session log + recent context
2. **Modify:** `HandoffManager._craft_handoff()` — use HandoffAgent instead of plan dump
3. **Modify:** `HandoffManager._build_resume_prompt()` — return handoff doc directly (no cold-start injection)
4. **Remove:** call to `librarian.get_cold_start_context()` in resume flow

## Success Criteria

- Handoff doc is ≤30 lines and contains file paths, function names, test commands
- Resume prompt contains zero injected library context
- Agent successfully continues work from handoff without human re-explanation
- No regression in `kadmon continue` behavior (existing sessions still resume)
