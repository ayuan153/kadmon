# Confidence-Gated Actions

## Overview

Kadmon self-assesses confidence before every action and routes accordingly: act silently when certain, narrate when choosing between alternatives, ask when genuinely uncertain. Unlike Claude Code (user picks a mode) or Cline (user configures per-category toggles), the agent adapts its autonomy level dynamically — no user configuration needed. The burden shifts from "user sets the right mode" to "agent knows when it's unsure."

## Confidence Spectrum

| Level | Internal signal | Behavior | Examples |
|-------|----------------|----------|----------|
| **HIGH** | "I know exactly what to do and it's routine" | Act silently | Creating a file, running tests, reading code, syntactic fixes |
| **MEDIUM** | "Reasonable approach but alternatives exist" | Act but narrate the decision | Choosing between implementations, picking a library, structuring a module |
| **LOW** | "Not sure what the user wants or multiple valid directions" | Call `ask_human` | Ambiguous requirements, architectural decisions, unclear scope, risky destructive actions |

## Confidence Assessment (Prompt-Guided Self-Assessment)

Not a separate classifier (too slow/expensive). Not a hardcoded allowlist. The agent evaluates its own certainty inline.

**Signals that LOWER confidence:**
- Multiple valid interpretations of the requirement
- No clear precedent in the codebase
- Destructive or hard-to-reverse action
- First time doing something in this project
- User's request is vague or open-ended

**Signals that RAISE confidence:**
- Clear, specific instruction
- Established pattern in the codebase to follow
- Reversible action (checkpoint exists)
- Routine mechanical operation

## Implementation

### Phase A — Prompt Rewrite (ship now)

Add to `SYSTEM_PROMPT` and `EDITOR_PROMPT`:

```
Before each action, assess your confidence that this is what the user wants:

HIGH — Clear instruction, established pattern, routine/reversible. Act without commentary.
MEDIUM — Reasonable approach but you're choosing between alternatives. Act, but briefly
  state your reasoning: "Going with X because Y." This lets the user redirect without
  being asked a question.
LOW — Ambiguous requirement, multiple valid directions, or risky/irreversible action with
  unclear intent. Use ask_human. Ask about DIRECTION, never about permission to act.

You are not asking "can I edit this file?" (that's always yes). You're asking "is this
the right file to edit?" only when you genuinely don't know.
```

### Phase B — Structured Tags (later, observability)

Agent emits confidence inline: `[HIGH] editing src/api.py`, `[MEDIUM] choosing REST — existing API is REST-based`, `[LOW] unclear if this needs a new service`. System can intercept LOW tags and force `ask_human` as a safety net. This is observability, not a gate.

### Phase C — Calibration from Feedback (research)

Track: did the user override a MEDIUM decision? Say "that's not what I meant" after a HIGH action? Use this signal to fine-tune the rubric over time.

## Interaction with ask_human

`ask_human` remains the mechanism for LOW-confidence moments. This framework improves *when* the agent invokes it. Current failure modes: asking permission for mechanics (too much) or guessing on ambiguous requirements (too little). After: asks only about genuine directional uncertainty.

## The "Narrate" Behavior

At MEDIUM confidence, the agent thinks out loud: *"I'm going with a REST endpoint here since the existing API is REST-based."* This is a senior dev pairing — stating decisions without blocking on approval. The user can interrupt if the direction is wrong. Implementation is purely prompt-guided.

## What This Is NOT

- **Not a permission system** — user never configures modes or approvals
- **Not a safety classifier** — destructive action review is a separate concern
- **Not a replacement for verification** — confidence in approach ≠ confidence code works
- **Not binary** — it's a spectrum with narration in the middle

## Success Metrics

1. Fewer unnecessary `ask_human` calls (no asking about mechanics)
2. Fewer "wrong direction" situations (asks before committing to wrong path)
3. Users feel informed without interruption (narration at MEDIUM)
4. `ask_human` calls are consistently high-quality directional questions
