# Parallel Workers

## Overview

Kadmon is single-threaded: one AgentLoop, one task, sequential tool calls. Parallel workers let the orchestrator fan out independent subtasks to separate context windows, execute concurrently, and merge results back. Inspired by Claude Code's Agent Teams and Cline's subagents.

## When to Parallelize

**Do parallelize:**
- Independent research — "read modules A, B, C to understand the system"
- Independent edits — "update these 3 test files with the new interface"
- Bulk analysis — "check each service for the deprecated pattern"

**Do NOT parallelize:**
- Tasks with dependencies — "implement A, then B which uses A's output"
- Tasks requiring shared state or coordination between steps

## Architecture

```
Main Agent (orchestrator)
  │  identifies independent subtasks during architect phase
  ├─► Worker 1 (own AgentLoop, fresh context, focused prompt)
  ├─► Worker 2
  └─► Worker 3
  │  concurrent execution (threading)
  ◄── results collected, synthesized into main context
```

Each worker gets: fresh context window, full tool registry (shared filesystem), a focused subtask prompt, and a bounded iteration budget (max_iterations=15).

## Interface

```python
@dataclass
class WorkerResult:
    task: str
    output: str           # final text response or patch
    success: bool
    files_modified: list[str]

class WorkerPool:
    def __init__(self, provider, repo_root, max_workers=3): ...
    def dispatch(self, tasks: list[str]) -> list[WorkerResult]: ...
```

## Triggering Parallelism

New tool: `parallel_dispatch` — the agent explicitly calls it with a list of independent subtask descriptions. Workers execute concurrently, results return as structured tool output. The agent synthesizes and continues.

The agent decides when to parallelize — no auto-detection.

## Constraints

- **Shared filesystem** — file conflicts possible; last write wins (Phase C adds detection)
- **No shared context** — workers are isolated, cannot see each other's progress
- **Max 3 concurrent workers** — controls cost and rate limits
- **15 iterations per worker** — bounded to prevent runaway spend
- **Threading, not multiprocessing** — LLM calls are I/O-bound

## What NOT to Do

- Don't auto-parallelize (agent must explicitly choose via tool call)
- Don't share context between workers (isolation is the point)
- Don't use multiprocessing (unnecessary overhead for I/O-bound work)
- Don't allow unbounded worker iterations

## Implementation Plan

| Phase | Scope |
|-------|-------|
| A | `WorkerPool` class + `parallel_dispatch` tool registration |
| B | Prompt guidance teaching the agent when/how to parallelize |
| C | File conflict detection and resolution (diff-based merge or retry) |

## Success Criteria

- 2-3x wall-clock speedup on independent multi-file tasks
- No correctness regression on sequential tasks
- Agent correctly avoids parallelizing dependent subtasks
- Cost per task increases ≤30% (bounded iterations prevent blowup)
