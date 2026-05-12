# Dual-Layer Session Persistence

## Problem

Kadmon currently relies on the agent calling `library_write` to persist learnings. This is fragile:
- If context degrades, the agent may forget to save
- Inline writes are fragmented (one learning at a time, no holistic view)
- Session state depends on the LLM remembering to act

Meanwhile, the session tracker captures structured data (plan steps, delegations) but doesn't feed it back into the library. There's a gap between "what happened" and "what kadmon remembers."

## Design: Separate Capture from Curation

Two layers working together:

### Layer 1: Mechanical Write (Deterministic)

An append-only structured log that captures every significant event during a session — no LLM involved, never loses data.

Storage: `.kadmon/sessions/log.jsonl` (one JSON object per line)

Events captured:
- Session start (task, timestamp, cwd)
- Plan creation (goal, steps)
- Plan step completion (step_id, status, files_touched)
- Tool calls with outcomes (tool_name, key args, success/failure)
- Errors and recovery attempts
- Session end (status, duration)

This is the "flight recorder" — like git reflog vs git log. It captures everything mechanically so nothing is lost regardless of agent behavior.

Implementation: Hook into the agent loop's `_process_response` method. After each tool execution, append a log entry. No LLM call, no synthesis, just structured JSON.

### Layer 2: Intelligent Curation (LLM-Powered)

Runs BETWEEN sessions (on session end, or on next cold start) to compress the raw log into clean library knowledge.

Three-step pipeline:
1. **Compress**: Read the raw session log, extract key learnings (patterns discovered, decisions made, architecture notes, gotchas encountered)
2. **Merge**: Feed extracted learnings into the existing Write Agent — synthesizes with existing library files, deduplicates, updates
3. **Prune**: Run the existing Prune Agent — archive completed sessions, remove stale entries, keep library lean

This is the "librarian curator" — it has the full session context (not just one learning at a time) so synthesis quality is higher.

## Architecture

```
During session:
  Agent works → Mechanical logger appends to log.jsonl
                (guaranteed, no LLM, no agent cooperation needed)

On session end (or next cold start):
  Curator Agent reads log.jsonl
    → Compress: extracts learnings from raw events
    → Merge: Write Agent updates library/*.md
    → Prune: Prune Agent archives/cleans
    → Clears log.jsonl (or archives it)

On session start:
  Read Agent synthesizes from library/*.md
    (already implemented — no changes needed)
```

## Session Discovery (Cross-Project)

Inspired by OMKC's central session index:

Storage: `~/.kadmon/sessions/index.json` (central, not per-project)

Index entry per session:

```json
{
  "session_key": "a1b2c3d4",
  "repo": "/path/to/project",
  "task": "Fix auth module token refresh",
  "started": "2026-05-12T10:00:00Z",
  "last_updated": "2026-05-12T11:30:00Z",
  "status": "completed",
  "files_touched": ["src/auth/refresh.py", "tests/test_auth.py"]
}
```

Discovery on cold start:
1. Check index for sessions matching current `cwd` (primary — no LLM needed)
2. If match found, check recency (< 2 weeks)
3. Load library context via Read Agent (already works)

This replaces the current approach of using the Index Agent to determine if `sessions/current.md` is related — the mechanical match by repo path is faster and more reliable. The Index Agent still handles relevance within the library (which files matter for this task), but session discovery is deterministic.

## What Changes From Current Design

| Current | Proposed |
|---------|----------|
| Agent calls `library_write` inline (unreliable) | Mechanical log captures everything (reliable) |
| Write Agent runs per-learning (fragmented) | Curator runs per-session (holistic) |
| Prune Agent runs on orthogonal detection only | Curator runs on every session end |
| No raw log exists | Raw log is source of truth |
| Session discovery requires LLM (Index Agent) | Repo-path matching is deterministic |
| Per-project sessions only | Central index enables cross-project awareness |

## What Stays The Same

- Library file format (markdown, human-readable)
- Read Agent (synthesizes on demand — no changes)
- Write Agent (merges knowledge — now called by Curator instead of inline)
- Prune Agent (archives/cleans — now part of Curator pipeline)
- `library_read` tool (agent still queries on demand)
- `library_write` tool (still available for explicit mid-session saves)
- `library_status` tool (still shows library contents + token usage)

## Implementation Plan

### Phase 1: Mechanical Logger

- [ ] Create `kadmon/memory/session_log.py` — SessionLogger class with `append(event)` method
- [ ] Define event types (session_start, plan_created, step_completed, tool_executed, session_end)
- [ ] Hook into AgentLoop._process_response to log tool executions
- [ ] Hook into PlanTool to log plan creation and step updates
- [ ] Log file: `.kadmon/sessions/log.jsonl`

### Phase 2: Curator Agent

- [ ] Create `kadmon/memory/agents/curator_agent.py` — orchestrates compress → merge → prune
- [ ] Compress step: reads log.jsonl, one LLM call to extract learnings
- [ ] Merge step: feeds learnings to existing Write Agent
- [ ] Prune step: calls existing Prune Agent
- [ ] Trigger: on session completion (in session_tracker.complete_session)
- [ ] Fallback trigger: on next cold start if previous session wasn't curated

### Phase 3: Central Index

- [ ] Create `~/.kadmon/sessions/index.json` with cross-project session entries
- [ ] Update session_tracker to write index entries on start/complete
- [ ] Cold start: check index for matching repo before calling Index Agent
- [ ] `kadmon status --global` to show all recent sessions across projects

## Cost Analysis

Curator runs once per session:
- Compress call: ~2000 tokens in (log), ~500 out (learnings) = ~$0.008
- Merge: reuses Write Agent (~$0.005)
- Prune: reuses Prune Agent (~$0.008)

**Total: ~$0.02 per session end** — same as current library overhead, but with guaranteed capture.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Log format | JSONL (append-only) | Fast writes, no parsing needed until curation, easy to stream |
| Curation timing | Session end (+ fallback on cold start) | Full context available, doesn't slow down active work |
| Central vs per-project index | Central (~/.kadmon/) | Enables cross-project discovery without scanning all repos |
| Keep library_write tool | Yes | Agent can still explicitly save mid-session; curator is the safety net |
| Mechanical logger location | Agent loop (not tools) | Captures all tool calls regardless of which tools are registered |
