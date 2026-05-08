"""Librarian: manages the file-based memory library."""

import time
from pathlib import Path


class Librarian:
    """Manages .kadmon/library/ for persistent cross-session knowledge."""

    def __init__(self, repo_root: str):
        self.library_path = Path(repo_root) / ".kadmon" / "library"
        self.library_path.mkdir(parents=True, exist_ok=True)
        (self.library_path / "tasks").mkdir(exist_ok=True)
        (self.library_path / "tasks" / "completed").mkdir(exist_ok=True)

    def load_relevant(self, task: str) -> str:
        """Load library entries relevant to the current task.

        Returns a formatted string of relevant context to inject into the agent.
        Uses keyword matching against file contents.
        """
        entries = []

        # Always load conventions and architecture if they exist
        for name in ["conventions.md", "architecture.md"]:
            path = self.library_path / name
            if path.exists():
                content = path.read_text().strip()
                if content:
                    entries.append(
                        f"## {name.replace('.md', '').title()}\n\n{content}"
                    )

        # Load decisions if task mentions relevant keywords
        decisions_path = self.library_path / "decisions.md"
        if decisions_path.exists():
            content = decisions_path.read_text().strip()
            if content:
                entries.append(f"## Decisions\n\n{content}")

        # Load current task context
        current_task = self.library_path / "tasks" / "current.md"
        if current_task.exists():
            content = current_task.read_text().strip()
            if content:
                entries.append(f"## Previous Task Context\n\n{content}")

        if not entries:
            return ""

        return "# Library Context\n\n" + "\n\n---\n\n".join(entries)

    def save_learning(self, category: str, content: str):
        """Save a learning to the appropriate library file.

        Categories: 'architecture', 'decisions', 'conventions', or custom.
        Appends to the file with a timestamp.
        """
        valid_categories = {"architecture", "decisions", "conventions"}
        if category not in valid_categories:
            category = "conventions"  # Default bucket

        path = self.library_path / f"{category}.md"
        timestamp = time.strftime("%Y-%m-%d %H:%M")
        entry = f"\n\n### [{timestamp}]\n\n{content.strip()}\n"

        with open(path, "a") as f:
            f.write(entry)

        self._update_index()

    def save_task_context(self, task: str, context: str):
        """Save current task state for handoff or next session."""
        path = self.library_path / "tasks" / "current.md"
        content = (
            f"# {task}\n\n"
            f"Updated: {time.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"{context.strip()}\n"
        )
        path.write_text(content)

    def complete_task(self, task: str, summary: str):
        """Archive current task to completed/ and clear current.md."""
        current = self.library_path / "tasks" / "current.md"
        if current.exists():
            slug = task.lower()[:50].replace(" ", "-").replace("/", "-")
            slug = "".join(c for c in slug if c.isalnum() or c == "-")
            dest = self.library_path / "tasks" / "completed" / f"{slug}.md"
            content = current.read_text()
            content += f"\n\n## Completion Summary\n\n{summary}\n"
            dest.write_text(content)
            current.write_text("")  # Clear current

        self._update_index()

    def get_cold_start_context(self) -> str:
        """Build context for a fresh session from library.

        Returns a concise summary suitable for injecting at session start.
        """
        parts = []

        # Project conventions (always useful)
        conv = self.library_path / "conventions.md"
        if conv.exists() and conv.stat().st_size > 0:
            parts.append(
                f"**Conventions:**\n{conv.read_text().strip()[-2000:]}"
            )

        # Architecture overview
        arch = self.library_path / "architecture.md"
        if arch.exists() and arch.stat().st_size > 0:
            parts.append(
                f"**Architecture:**\n{arch.read_text().strip()[-2000:]}"
            )

        # Current task (if any)
        current = self.library_path / "tasks" / "current.md"
        if current.exists() and current.stat().st_size > 0:
            parts.append(
                f"**Current Task:**\n{current.read_text().strip()[-3000:]}"
            )

        if not parts:
            return ""

        return "# Project Memory (from .kadmon/library/)\n\n" + "\n\n".join(parts)

    def _update_index(self):
        """Rebuild index.md from library contents."""
        lines = ["# Library Index\n"]

        for path in sorted(self.library_path.glob("*.md")):
            if path.name == "index.md":
                continue
            size = path.stat().st_size
            if size > 0:
                lines.append(f"- [{path.name}]({path.name}) ({size} bytes)")

        tasks_dir = self.library_path / "tasks"
        current = tasks_dir / "current.md"
        if current.exists() and current.stat().st_size > 0:
            lines.append(
                "- [tasks/current.md](tasks/current.md) (active task)"
            )

        completed = list((tasks_dir / "completed").glob("*.md"))
        if completed:
            lines.append(
                f"- tasks/completed/ ({len(completed)} archived tasks)"
            )

        (self.library_path / "index.md").write_text("\n".join(lines) + "\n")
