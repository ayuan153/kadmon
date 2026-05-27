# Workflow Discipline

## Philosophy

Kadmon's autonomy comes from disciplined workflow, not session persistence. The agent follows a structured process that produces clean artifacts (docs, tests, handoff) — these artifacts ARE the persistence mechanism. A fresh agent with good docs is better than a stale agent with accumulated context.

The workflow:
```
Plan & Design → Execute (with continuous questions) → Verify & Lock In → Reflect & Document → Handoff
```

## The Five Behaviors

### 1. Plan First (Nontrivial Tasks)

**Trigger:** Task has design implications OR touches multiple files.

**Behavior:** Before any code changes, the agent:
- Explores the codebase to understand the current state
- Writes a design/plan document (can be brief for moderate tasks, detailed for complex ones)
- Surfaces open questions about the approach
- Waits for human confirmation before executing

**NOT triggered for:** One-line fixes, typo corrections, single-file changes with obvious implementation.

**Implementation:** Prompt guidance in ARCHITECT_PROMPT. The existing architect/editor phase separation already supports this — strengthen the prompt to make doc-writing the default output of architect phase for nontrivial tasks.

### 2. Surface Open Questions Continuously

**Behavior:** On EVERY response where the agent has uncertainty, it surfaces questions. Not just at the start — continuously throughout execution.

This is NOT "ask all questions upfront then go silent." It's "pause and surface ambiguities as they arise."

**Format:** At the end of any response where the agent has open questions:
```
**Open questions:**
- [question about direction/approach]
- [question about ambiguous requirement]
```

**When NOT to ask:** When the agent is HIGH confidence on all aspects of what it's doing. Don't ask for the sake of asking.

**Implementation:** Add to SYSTEM_PROMPT: "If you have open questions about direction, approach, or requirements at any point, surface them at the end of your response. Don't wait — ask as they arise."

### 3. Verify & Lock In (Tests as Spec)

**Core principle:** Tests define correct behavior. Code implements it.

**Test failure decision tree:**
1. Is the test asserting correct expected behavior? (Check the design, ask if unclear)
2. If YES → the code is wrong. Fix the code, not the test.
3. If NO → the test is wrong. Fix the assertion to match correct behavior.

**NEVER:**
- Weaken a test assertion to make it pass
- Change a test to assert what the code currently does when the code is wrong
- Ship a fix without a test that reproduces the bug

**Lock-in workflow:**
- New behavior → write test first that captures the desired behavior, then implement
- Bug fix → write test that reproduces the bug (fails), fix the bug, test passes
- Commit fix AND test together

**Implementation:** Add the decision tree to EDITOR_PROMPT. This is the strongest behavioral rule — it overrides the agent's instinct to "make tests pass."

### 4. Reflect & Document

**Trigger:** After execution is complete and verified.

**Behavior:**
- Update any design docs that were written during planning (if implementation diverged)
- Update README if the change affects user-facing behavior
- Update AGENTS.md if new conventions were established
- Note any remaining TODOs or known limitations

**Implementation:** Prompt guidance in EDITOR_PROMPT's post-completion phase.

### 5. Auto-Detect Handoff Points

**Trigger heuristics:**
- Reached a satisfying stopping point after a bug-fixing/iteration cycle
- Next steps are a clean break from previous work (different module, different concern)
- Context is getting long and the remaining work is independent of what was discussed

**Behavior when triggered:**
- Offer to write a handoff: "We've reached a good stopping point. Want me to write a handoff doc for the next session?"
- If yes: write handoff doc with pointers to relevant docs, background context, and a clear next-step prompt
- The handoff doc is NOT compaction — it's a lean task brief that references docs (which contain the real detail)

**Handoff doc structure:**
```markdown
# Handoff: [topic]

## Background
[1-2 sentences + pointer to design doc if one exists]

## What's Done
[completed work with file paths]

## What's Next
[specific next steps]

## Key Files
[file paths the next agent should read]

## How to Verify
[test commands]
```

**Implementation:** The existing HandoffMonitor detects token budget and quality degradation. Add a new trigger: "task boundary with clean break" — detected when the plan is complete and the agent's next suggested action is in a different area of the codebase.

## Session Resumption (OMKC-Inspired)

When kadmon starts and a previous handoff exists:

1. Check if `.kadmon/handoffs/latest.md` exists and is recent (<2 weeks)
2. Check if the user's prompt is low-detail (short, vague) vs high-detail (specific task)
3. If handoff exists AND prompt is low-detail:
   - Present a brief summary: "Previous session worked on [X]. Continue from there, or start fresh?"
   - If continue: load handoff doc as context
   - If fresh: ignore handoff
4. If prompt is high-detail: start fresh (user knows what they want)

**Key principle:** When in doubt, start fresh. Old context is more likely to be noise than signal.

## Implementation Priority

1. **Prompt rewrites** — bake all 5 behaviors into SYSTEM/ARCHITECT/EDITOR prompts
2. **Test failure decision tree** — strongest behavioral rule, add to EDITOR_PROMPT
3. **Open questions as default** — add to SYSTEM_PROMPT
4. **Handoff point detection** — extend HandoffMonitor with "clean break" heuristic
5. **Session resumption** — lightweight check on startup

## Success Criteria

1. Agent writes design docs before implementing nontrivial tasks (without being asked)
2. Agent surfaces open questions continuously (not just at start)
3. Agent fixes code when tests fail, not tests (unless assertions are genuinely wrong)
4. Agent offers handoff at natural stopping points
5. A fresh agent with the handoff doc can continue work without re-explanation
6. User never has to prompt "ask me any open questions" — agent does it by default
