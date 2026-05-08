"""Pruner: strips irrelevant context on task pivot, archives old library entries."""

from pathlib import Path

from kadmon.agent.planner import Plan, StepStatus


class Pruner:
    """Strips irrelevant context when tasks pivot or handoff occurs."""

    def prune_for_handoff(self, plan: Plan | None, new_task: str = "") -> str:
        """Extract only what's relevant for continuation.

        Returns a concise summary of completed work + what matters for next steps.
        Drops: verbose tool outputs, exploration dead-ends, failed approach details.
        Keeps: what was accomplished, key decisions, remaining work.
        """
        if not plan:
            return ""

        parts = []

        # Summarize completed work (what, not how)
        done = [s for s in plan.steps if s.status == StepStatus.DONE]
        if done:
            parts.append("Completed:")
            for s in done:
                parts.append(f"- {s.description}")

        # Note failed approaches (so we don't repeat them)
        failed = [s for s in plan.steps if s.status == StepStatus.FAILED]
        if failed:
            parts.append("\nFailed approaches (don't retry):")
            for s in failed:
                note = f" — {s.notes}" if s.notes else ""
                parts.append(f"- {s.description}{note}")

        # Remaining work
        pending = [s for s in plan.steps if s.status in (StepStatus.PENDING, StepStatus.ACTIVE)]
        if pending:
            parts.append("\nRemaining:")
            for s in pending:
                parts.append(f"- {s.description}")

        if not parts:
            return ""

        return "\n".join(parts)

    def prune_library(self, library_path: Path, current_task: str = ""):
        """Archive completed task entries, keep only relevant active content.

        Moves tasks/current.md to tasks/completed/ if it doesn't match current_task.
        """
        tasks_dir = library_path / "tasks"
        current_file = tasks_dir / "current.md"

        if not current_file.exists() or current_file.stat().st_size == 0:
            return

        content = current_file.read_text()

        # If current task file is about a different task, archive it
        if current_task and current_task.lower() not in content.lower():
            # Archive to completed/
            completed_dir = tasks_dir / "completed"
            completed_dir.mkdir(exist_ok=True)

            # Extract task name from first heading or use generic name
            first_line = content.split("\n")[0].strip("# ").strip()
            slug = first_line.lower()[:50].replace(" ", "-")
            slug = "".join(c for c in slug if c.isalnum() or c == "-") or "archived-task"

            dest = completed_dir / f"{slug}.md"
            # Don't overwrite existing archives
            if dest.exists():
                import time

                slug += f"-{int(time.time())}"
                dest = completed_dir / f"{slug}.md"

            dest.write_text(content)
            current_file.write_text("")  # Clear current

    def summarize_completed_work(self, plan: Plan) -> str:
        """One-paragraph summary of what was accomplished (not how).

        Used for library entries and handoff docs.
        """
        done = [s for s in plan.steps if s.status == StepStatus.DONE]
        if not done:
            return "No steps completed."

        descriptions = [s.description for s in done]
        if len(descriptions) == 1:
            return f"Completed: {descriptions[0]}"

        summary = "Completed " + str(len(descriptions)) + " steps: "
        summary += "; ".join(descriptions[:5])
        if len(descriptions) > 5:
            summary += f"; and {len(descriptions) - 5} more"
        return summary
