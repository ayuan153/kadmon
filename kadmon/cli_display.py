"""Display layer for streaming agent output in the terminal."""

import sys

from rich.console import Console
from rich.markup import escape

from kadmon.providers.base import StreamChunk, StreamEvent

console = Console()


class StreamDisplay:
    """Renders streaming events to the terminal."""

    def __init__(self):
        self._in_text = False
        self._tool_depth = 0

    def handle(self, chunk: StreamChunk):
        """Handle a single stream chunk."""
        if chunk.event == StreamEvent.TEXT_DELTA:
            self._handle_text(chunk.text)
        elif chunk.event == StreamEvent.TOOL_START:
            self._handle_tool_start(chunk.tool_name)
        elif chunk.event == StreamEvent.TOOL_DELTA:
            pass  # Don't show raw JSON streaming
        elif chunk.event == StreamEvent.TOOL_END:
            self._handle_tool_end(chunk.tool_name)
        elif chunk.event == StreamEvent.DONE:
            self._handle_done()

    def show_tool_result(self, tool_name: str, output: str, is_error: bool = False):
        """Show the result of a tool execution."""
        if is_error:
            console.print(f"  [red]✗ {escape(output[:200])}[/red]")
        else:
            # Show truncated output for most tools
            lines = output.strip().split("\n")
            if len(lines) <= 5:
                for line in lines:
                    console.print(f"  [dim]{escape(line)}[/dim]")
            else:
                for line in lines[:3]:
                    console.print(f"  [dim]{escape(line)}[/dim]")
                console.print(f"  [dim]... ({len(lines) - 3} more lines)[/dim]")

    def show_submit(self, patch: str):
        """Show that a patch was submitted."""
        lines = patch.strip().split("\n")
        console.print(f"\n[green bold]✓ Patch generated ({len(lines)} lines)[/green bold]")

    def _handle_text(self, text: str):
        if not self._in_text:
            self._in_text = True
        sys.stdout.write(text)
        sys.stdout.flush()

    def _handle_tool_start(self, tool_name: str):
        if self._in_text:
            sys.stdout.write("\n")
            self._in_text = False
        console.print(f"  [cyan]⚡ {tool_name}[/cyan]", end="")
        self._tool_depth += 1

    def _handle_tool_end(self, tool_name: str):
        self._tool_depth -= 1
        # Tool name was already printed at start; just finish the line
        console.print("")

    def _handle_done(self):
        if self._in_text:
            sys.stdout.write("\n")
            self._in_text = False
