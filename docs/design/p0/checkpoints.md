# Checkpoints & Rewind

## Overview

Two separate mechanisms serving different actors:

1. **File checkpoints** — agent-facing. Snapshot files before edits, rollback autonomously on test failure. Invisible to user unless they need the escape hatch.
2. **Conversation rewind** — user-facing. Rewind chat to before prompt N, re-prompt with different direction. Files stay as-is by default.

These are decoupled. Conversation rewind does NOT revert files (unless explicitly requested). File rollback does NOT affect conversation.

## Part 1: File Checkpoints (Agent-Facing)

### Goal

Agent can recover from bad edits without human intervention: edit → test → fail → rollback → try differently.

### Architecture

```
.kadmon/checkpoints/
├── 0001/
│   ├── meta.json          # {"id": "0001", "tool": "edit_file", "files": ["src/foo.py"]}
│   └── files/
│       └── src/foo.py     # Content BEFORE the edit
├── 0002/
│   └── ...
```

- Sequence-numbered, monotonic within session
- Only files about to be modified are stored
- Max 20 checkpoints, auto-prune oldest
- Cleared on session start

### Implementation

- `CheckpointManager` class: `create(files, tool)`, `rollback(id)`, `list()`, `clear()`
- Hooked into `WriteFileTool` and `EditFileTool` — snapshot before write
- New tool: `checkpoint_rollback` — agent uses when tests fail after an edit
- No checkpoint for new files (nothing to rollback to)

### User escape hatch

- `kadmon rollback [id]` — CLI command for manual file rollback
- `kadmon checkpoints` — list available file checkpoints

## Part 2: Conversation Rewind (User-Facing)

### Goal

User can say "wrong direction, go back" without losing file changes they want to keep. Rewind conversation to before prompt N, re-prompt.

### Architecture

```
.kadmon/conversation/
├── turn_001.json    # {"prompt": "fix auth bug", "context_snapshot": [...], "plan_snapshot": {...}}
├── turn_002.json
├── ...
```

- Snapshot taken at each user prompt (before agent processes it)
- Stores: user prompt text, full message context, plan state
- Last 10 turns retained, older pruned
- Cleared on session end

### Implementation

- `ConversationHistory` class: `snapshot(prompt, context, plan)`, `rewind(turn_id)`, `list_turns()`
- Hooked into `AgentLoop.run()` / the chat REPL — snapshot before each agent.run(task)
- `rewind()` returns the restored context + plan; the REPL replaces agent state and waits for new input

### UX

```
$ kadmon rewind
Recent prompts:
  [3] "add pagination to /users endpoint"
  [2] "fix the auth token refresh bug"
  [1] "refactor the database layer"

Rewind to before which prompt? [1-3]: 3
✓ Conversation restored to after prompt 2. Files unchanged.
> _
```

### Combined rewind (opt-in)

```
$ kadmon rewind --with-files
```

Restores conversation AND rolls back all file checkpoints created after that turn. Nuclear option for "undo everything since then."

## What We Don't Do

- Don't couple file and conversation rewind by default
- Don't use shadow git (file copies are simpler, isolated from user's git)
- Don't persist checkpoints across sessions (handoff handles cross-session continuity)
- Don't show checkpoints inline during work (agent handles its own recovery silently)

## Competitive Comparison

| Capability | Cline | Claude Code | Kadmon |
|-----------|-------|-------------|--------|
| File rollback | ✅ per tool call | ✅ per prompt | ✅ per tool call |
| Conversation rewind | ✅ | ✅ | ✅ |
| Decoupled (files vs convo) | ✅ (3 options) | ✅ (4 options) | ✅ (separate by default) |
| Agent self-rollback | ❌ (user-initiated only) | ❌ | ✅ (autonomous on test failure) |
| Diff view | ✅ (VS Code) | ❌ | `kadmon diff` (planned) |

Kadmon's differentiator: the agent uses file checkpoints autonomously for recovery. Users rarely need to intervene. But when they do, `kadmon rewind` (conversation) and `kadmon rollback` (files) are there.

## Implementation Order

1. File checkpoints + CheckpointManager + checkpoint_rollback tool
2. Conversation rewind + ConversationHistory + `kadmon rewind` CLI
3. `kadmon diff` (nice-to-have, shells out to diff)
4. `--with-files` combined rewind

## Success Criteria

1. Agent recovers from bad edits autonomously (test fail → rollback → retry)
2. User can rewind conversation without losing file changes
3. User can optionally rewind both together
4. User's git is never affected
5. Storage bounded, auto-pruned, session-scoped
