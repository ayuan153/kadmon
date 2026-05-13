# Design: AGENTS.md Support

## Overview

Kadmon should automatically ingest a repo's `AGENTS.md` file into its library system on first session, and detect staleness on subsequent sessions. This aligns Kadmon with the cross-tool standard used by Claude Code, Codex, and Cline for repo-level AI instructions.

## Behavior

- **First session:** If `AGENTS.md` exists at repo root and hasn't been ingested, read it and merge into library via `WriteAgent.update("conventions", content)`.
- **Subsequent sessions:** Already in library. No re-read unless file changed.
- **Staleness detection:** Compare SHA-256 of `AGENTS.md` against stored hash in `.kadmon/agents_md_hash`. If different → re-ingest.

## Implementation

**Where:** Librarian cold-start path (before the agent loop begins).

**Flow:**
1. Check if `AGENTS.md` exists at repo root. If not, skip.
2. Compute SHA-256 of file contents.
3. Read `.kadmon/agents_md_hash`. If matches, skip.
4. Read `AGENTS.md`, call `WriteAgent.update("conventions", content)`.
5. Write new hash to `.kadmon/agents_md_hash`.

**Storage:** `.kadmon/agents_md_hash` — plain text file containing the hex digest.

## What NOT To Do

- Don't inject `AGENTS.md` as a raw system-prompt blob.
- Don't re-read every session if unchanged.
- Don't create `AGENTS.md` if it doesn't exist.
- Don't store the full file contents in `.kadmon/` (library handles that).

## Success Criteria

- `kadmon` in a repo with `AGENTS.md` → conventions appear in library after first session.
- Editing `AGENTS.md` → next session picks up changes.
- No `AGENTS.md` → no error, no action.
- Unchanged `AGENTS.md` → no redundant writes to library.
