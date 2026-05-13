# Path-Scoped Library Rules

## Overview

Library entries can declare a `Scope:` header with glob patterns so they only load when the agent is working on matching files. Unscoped entries remain globally relevant. This reduces noise and makes library lookups contextually precise.

## Scope Header Format

```markdown
# Authentication Patterns
Scope: src/auth/**, tests/test_auth*

## Summary
Always use token rotation for refresh tokens...
```

Comma-separated globs, evaluated against project root. No `Scope:` line = global entry (backward compatible).

## How IndexAgent Uses Scope

1. `library_read(query)` is called with an additional `active_files` list (files read/edited this session)
2. IndexAgent reads each library file's header (already does this for summaries)
3. For scoped entries: include only if ANY active file matches ANY of the entry's glob patterns
4. For unscoped entries: always include as candidates (existing behavior)

## How Scope Gets Set

- **WriteAgent** — adds `Scope:` when the learning is clearly about specific files/directories
- **Manual** — user edits the library file directly
- **CuratorAgent** — infers scope from session log (which files were touched when the learning was created)

## Implementation

1. `IndexAgent._read_file_headers()` — parse `Scope:` line into list of glob patterns
2. `IndexAgent.find_relevant()` — accept optional `active_files: list[str]`, filter scoped entries against it using `fnmatch`
3. `LibraryReadTool` — pass `session.active_files` to IndexAgent
4. `WriteAgent` prompt — instruct it to include `Scope:` when the topic is file-specific

## What NOT To Do

- Don't make scope mandatory — most entries should remain global
- Don't create a separate rules directory — use existing `.kadmon/library/`
- Don't load scoped entries that don't match — that's the entire point

## Success Criteria

- Scoped entry about auth is NOT returned when agent is editing `src/providers/openai.py`
- Scoped entry about auth IS returned when agent is editing `src/auth/tokens.py`
- Unscoped entries behave exactly as before (no regression)
- WriteAgent produces scoped entries for file-specific learnings without being told
