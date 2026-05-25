"""Tests for the `kadmon status` CLI command."""

from click.testing import CliRunner

from kadmon.cli import status
from kadmon.memory.librarian import Librarian
from kadmon.memory.session_tracker import SessionTracker


def test_status_no_kadmon_dir(tmp_path):
    """With no .kadmon directory the command should say so and exit cleanly."""
    runner = CliRunner()
    result = runner.invoke(status, ["--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert ".kadmon" in result.output
    assert "init" in result.output.lower() or "no .kadmon" in result.output.lower()


def test_status_no_active_session(tmp_path):
    """With .kadmon dir but no session.json the command reports no active session."""
    (tmp_path / ".kadmon").mkdir()
    runner = CliRunner()
    result = runner.invoke(status, ["--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "no active session" in result.output.lower()


def test_status_active_session(tmp_path):
    """Active session details (id, task, status) are printed."""
    tracker = SessionTracker(str(tmp_path))
    tracker.start("Build the feature")
    runner = CliRunner()
    result = runner.invoke(status, ["--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "Build the feature" in result.output
    assert "in_progress" in result.output
    assert tracker._session.session_id in result.output


def test_status_shows_delegations(tmp_path):
    """Delegations with summaries appear in the output."""
    tracker = SessionTracker(str(tmp_path))
    tracker.start("Parent task")
    tracker.start_delegation("d1", "worker", "Explore codebase")
    tracker.complete_delegation("d1", "Found 3 modules")
    tracker.start_delegation("d2", "worker", "Write tests")
    runner = CliRunner()
    result = runner.invoke(status, ["--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "Explore codebase" in result.output
    assert "Found 3 modules" in result.output
    assert "Write tests" in result.output


def test_status_shows_library_files(tmp_path):
    """Library files saved by Librarian appear in the output."""
    lib = Librarian(str(tmp_path))
    lib.save_learning("conventions", "Use type hints everywhere")
    runner = CliRunner()
    result = runner.invoke(status, ["--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "conventions.md" in result.output


def test_status_shows_session_history(tmp_path):
    """Archived sessions are counted and reported."""
    tracker = SessionTracker(str(tmp_path))
    tracker.start("Task 1")
    tracker.complete_session()
    tracker.start("Task 2")
    tracker.complete_session()
    runner = CliRunner()
    result = runner.invoke(status, ["--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "2 archived session" in result.output


def test_status_empty_library(tmp_path):
    """When library dir exists but is empty, a friendly message is shown."""
    (tmp_path / ".kadmon").mkdir()
    (tmp_path / ".kadmon" / "library").mkdir()
    runner = CliRunner()
    result = runner.invoke(status, ["--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "empty" in result.output.lower() or "library" in result.output.lower()
