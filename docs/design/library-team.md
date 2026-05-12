# Library Team: Design & Implementation Plan

## Overview

The Library Team is kadmon's context management system — a set of focused LLM-powered subagents that manage a file-based knowledge store. Instead of injecting the entire library into context (wasteful, polluting), the agent queries the library on demand and gets back focused, synthesized context.

This is kadmon's killer app: intelligent, autonomous context management that makes multi-session work seamless.

## Architecture

```
User prompt → Kadmon (orchestrator)
                 │
                 ├── library_read(task) ──→ [Index Agent] → [Read Agent] → focused context
                 │
                 ├── (works on task)
                 │
                 ├── library_write(learnings) ──→ [Write Agent] → synthesized update
                 │
                 └── (on pivot/handoff) ──→ [Prune Agent] → clean library
```

### Subagent Roles

| Agent | Purpose | Input | Output |
|-------|---------|-------|--------|
| **Index** | Find what's relevant | Task description | List of relevant file paths + relevance notes. Triggers prune if session is orthogonal. |
| **Read** | Synthesize into context | File paths + task | Concise summary + pointers for deeper reading |
| **Write** | Merge learnings | New knowledge + topic | Updated library file (synthesized, not appended) |
| **Prune** | Keep library lean | Current task context | Archived stale entries, merged duplicates |

### Key Principle: Each Subagent = One Focused LLM Call

These are not separate processes or long-running agents. Each is a single LLM call with:
- A focused system prompt defining its role
- Access to read/write the library files
- A specific input/output contract

## Library File Structure

```
.kadmon/library/
├── index.md              # Auto-maintained table of contents
├── project.md            # Project overview, architecture, tech stack
├── conventions.md        # Code patterns, naming, gotchas
├── decisions.md          # Key decisions with rationale
└── sessions/
    ├── current.md        # Active task state (what's in progress)
    └── archive/
        ├── fix-auth-bug.md
        └── add-pagination.md
```

Each file is markdown with a predictable structure:

```markdown
# Topic Name

## Summary
One-paragraph overview.

## Details
- Key point 1
- Key point 2

## Last Updated
2026-05-11
```

## Tool Interface (What Kadmon Sees)

### `library_read`

Called at the start of a task (and whenever the agent needs project context mid-task).

```
Input:  { "query": "What do I need to know about the auth module?" }
Output: "The auth module uses JWT with refresh tokens. Tokens are validated
         in middleware (src/middleware/auth.ts). Key decision: we chose
         stateless JWT over session-based auth for horizontal scaling.
         See: .kadmon/library/decisions.md for full rationale."
```

Internally:
1. Index Agent scans library, identifies relevant files
2. If session is orthogonal to previous task → triggers Prune automatically
3. Read Agent reads those files, synthesizes a focused response
4. Returns summary + pointers (not raw file contents)

### `library_write`

Called after completing a plan step or learning something important.

```
Input:  { "topic": "conventions", "content": "API endpoints use snake_case for query params, camelCase for JSON bodies" }
Output: "Updated conventions.md — merged with existing API conventions section."
```

Internally:
1. Write Agent reads existing file for the topic
2. Synthesizes new content with existing (deduplicates, merges, updates)
3. Writes the updated file
4. Updates index.md

### `library_status`

Quick check of what's in the library (no LLM call needed — just reads index.md).

```
Input:  {}
Output: "Library contains: project.md (1.2KB), conventions.md (800B), decisions.md (2.1KB), sessions/current.md (500B)"
```

## Subagent Prompts

### Index Agent

```
You are the Library Index agent. Your job is to determine which library files
are relevant to the user's current task.

You have access to the library at .kadmon/library/. Read index.md to see what's
available, then decide which files (if any) are relevant.

Rules:
- Return a list of relevant file paths with a one-line note on why each is relevant.
- If nothing is relevant, return empty list.
- If sessions/current.md describes work UNRELATED to the current task, note that
  the session is orthogonal (this triggers pruning).
- Be selective — only return files that will actually help with the current task.
```

### Read Agent

```
You are the Library Read agent. Your job is to read the specified library files
and synthesize them into concise, actionable context for the working agent.

Rules:
- Read the files you're given.
- Synthesize into a focused summary (max ~500 words).
- Include specific details that help with the task (file paths, function names, decisions).
- End with "For more detail, see: [file paths]" if the full files have more useful info.
- Do NOT return raw file contents — synthesize.
```

### Write Agent

```
You are the Library Write agent. Your job is to update the library with new knowledge.

Rules:
- Read the existing file for the topic (if it exists).
- MERGE the new content with existing content — do not just append.
- Deduplicate: if the new info overlaps with existing, update the existing entry.
- Keep entries concise and structured (use markdown headers, bullet points).
- Update the "Last Updated" timestamp.
- If the file doesn't exist, create it with proper structure.
```

### Prune Agent

```
You are the Library Prune agent. Your job is to keep the library lean and relevant.

Rules:
- Move sessions/current.md to sessions/archive/ (with a descriptive filename).
- If any library files have redundant or contradictory entries, merge them.
- If any entries are clearly stale (reference deleted files, outdated decisions), remove them.
- Update index.md after changes.
- Be conservative — when in doubt, keep the entry.
```

## Session Resume Flow

```
User starts kadmon, types a prompt
    ↓
Kadmon calls library_read(prompt)
    ↓
Index Agent checks sessions/current.md:
    ├── Related to prompt → Read Agent returns session context + relevant knowledge
    ├── Orthogonal to prompt → triggers Prune, returns only relevant project knowledge
    └── No current session → returns only relevant project knowledge
    ↓
Kadmon works with focused context (never sees the full library)
```

**Explicit resume:** `kadmon continue` skips the Index relevance check and loads `sessions/current.md` directly as the task.

## Implementation Plan

### Phase 1: Core Library Tools (Week 1)

Replace the current blob-injection `Librarian.load_relevant()` with the tool-based approach.

- [ ] **Refactor library tools** — Create `kadmon/tools/library.py` with `LibraryReadTool`, `LibraryWriteTool`, `LibraryStatusTool`
- [ ] **Index Agent** — `kadmon/memory/agents/index_agent.py`: takes query, reads index.md + file headers, returns relevant paths + orthogonality signal
- [ ] **Read Agent** — `kadmon/memory/agents/read_agent.py`: takes file paths + query, reads files, returns synthesized context
- [ ] **Write Agent** — `kadmon/memory/agents/write_agent.py`: takes topic + content, reads existing, merges, writes
- [ ] **Remove cold-start blob injection** — Delete the `load_relevant()` call from agent loop startup. Agent now calls `library_read` explicitly when it needs context.
- [ ] **Update system prompt** — Tell the agent about `library_read`/`library_write` tools and when to use them

### Phase 2: Prune Agent + Session Management (Week 2)

- [ ] **Prune Agent** — `kadmon/memory/agents/prune_agent.py`: archives stale sessions, merges redundant entries
- [ ] **Auto-prune on orthogonal session** — Index Agent triggers Prune when it detects the current task is unrelated to `sessions/current.md`
- [ ] **`kadmon continue` command** — Loads `sessions/current.md` directly as the task, bypasses Index relevance check
- [ ] **Graceful Ctrl+C** — On interrupt, Write Agent saves current progress to `sessions/current.md`

### Phase 3: Polish + Optimization (Week 3)

- [ ] **Token budget tracking** — Monitor how many tokens the library team uses per session
- [ ] **Caching** — If the same `library_read` query is made twice in a session, return cached result
- [ ] **Non-LLM Index fallback** — If library files follow predictable structure, Index can use keyword matching instead of LLM (saves one call per read)
- [ ] **Tests** — Unit tests for each agent, integration test for full read/write/prune cycle

## Cost Analysis

Per session (typical):
- 1 Index call (~500 tokens in, ~200 out) = ~$0.002
- 1 Read call (~2000 tokens in, ~500 out) = ~$0.008
- 1-2 Write calls (~1000 tokens in, ~500 out) = ~$0.005 each
- Occasional Prune (~2000 tokens in, ~500 out) = ~$0.008

**Total overhead: ~$0.02-0.03 per session** — negligible compared to the main agent work ($0.50-5.00 per task).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Subagent implementation | Focused LLM calls (not spawned processes) | Simple, fast, no orchestration overhead |
| Library format | Markdown files | Human-readable, git-friendly, LLM-friendly |
| Index approach | LLM-based (initially) | More flexible than keyword matching; can understand semantic relevance |
| Write strategy | Synthesize/merge (not append) | Prevents library bloat, keeps entries coherent |
| Session resume | Implicit via Index relevance | No manual "continue" needed for related work; explicit `kadmon continue` for full resume |
| Prune trigger | Automatic on orthogonal detection | User never has to manage library manually |
| Context injection | Never — agent queries on demand | Prevents pollution, agent controls what enters context |

## Relationship to Existing Code

| Current | Becomes |
|---------|---------|
| `Librarian.load_relevant()` (blob injection on cold start) | Removed — replaced by `library_read` tool |
| `Librarian.save_learning()` (append to file) | Replaced by Write Agent (synthesize/merge) |
| `Librarian.save_task_context()` | Replaced by Write Agent writing to `sessions/current.md` |
| `Pruner` class (rule-based) | Replaced by Prune Agent (LLM-based, smarter) |
| Cold start in `AgentLoop.run()` | Removed — agent calls `library_read` when it needs context |

## Inspiration

- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) — focused subagents with clear contracts
- [Anthropic: Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system) — specialized agents for different phases of work
- OMKC's session tracking — deterministic state management, orchestrator only reads
