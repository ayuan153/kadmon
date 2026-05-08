"""Tests for kadmon Phase 4a: Librarian and SessionTracker."""

import json

from kadmon.memory.librarian import Librarian
from kadmon.memory.session_tracker import SessionTracker


# === Librarian Tests ===


def test_librarian_init_creates_dirs(tmp_path):
    Librarian(str(tmp_path))
    assert (tmp_path / ".kadmon" / "library").is_dir()
    assert (tmp_path / ".kadmon" / "library" / "tasks").is_dir()
    assert (tmp_path / ".kadmon" / "library" / "tasks" / "completed").is_dir()


def test_save_learning(tmp_path):
    lib = Librarian(str(tmp_path))
    lib.save_learning("conventions", "Use black for formatting")
    path = tmp_path / ".kadmon" / "library" / "conventions.md"
    content = path.read_text()
    assert "Use black for formatting" in content
    assert "###" in content  # timestamp header


def test_save_learning_appends(tmp_path):
    lib = Librarian(str(tmp_path))
    lib.save_learning("conventions", "First entry")
    lib.save_learning("conventions", "Second entry")
    content = (tmp_path / ".kadmon" / "library" / "conventions.md").read_text()
    assert "First entry" in content
    assert "Second entry" in content


def test_load_relevant_empty(tmp_path):
    lib = Librarian(str(tmp_path))
    assert lib.load_relevant("some task") == ""


def test_load_relevant_with_content(tmp_path):
    lib = Librarian(str(tmp_path))
    lib.save_learning("conventions", "Use pytest")
    lib.save_learning("architecture", "Modular design")
    result = lib.load_relevant("implement feature")
    assert "Use pytest" in result
    assert "Modular design" in result


def test_save_task_context(tmp_path):
    lib = Librarian(str(tmp_path))
    lib.save_task_context("Build API", "Working on endpoints")
    path = tmp_path / ".kadmon" / "library" / "tasks" / "current.md"
    assert path.exists()
    content = path.read_text()
    assert "Build API" in content
    assert "Working on endpoints" in content


def test_complete_task(tmp_path):
    lib = Librarian(str(tmp_path))
    lib.save_task_context("Build API", "Working on endpoints")
    lib.complete_task("Build API", "All endpoints done")
    current = tmp_path / ".kadmon" / "library" / "tasks" / "current.md"
    assert current.read_text() == ""
    completed_files = list(
        (tmp_path / ".kadmon" / "library" / "tasks" / "completed").glob("*.md")
    )
    assert len(completed_files) == 1
    assert "All endpoints done" in completed_files[0].read_text()


def test_get_cold_start_context(tmp_path):
    lib = Librarian(str(tmp_path))
    lib.save_learning("conventions", "Use type hints")
    result = lib.get_cold_start_context()
    assert "Use type hints" in result
    assert "Project Memory" in result


def test_update_index(tmp_path):
    lib = Librarian(str(tmp_path))
    lib.save_learning("conventions", "Some convention")
    index = (tmp_path / ".kadmon" / "library" / "index.md").read_text()
    assert "conventions.md" in index


# === SessionTracker Tests ===


def test_session_start(tmp_path):
    tracker = SessionTracker(str(tmp_path))
    session = tracker.start("Implement feature X")
    assert (tmp_path / ".kadmon" / "session.json").exists()
    data = json.loads((tmp_path / ".kadmon" / "session.json").read_text())
    assert data["task"] == "Implement feature X"
    assert data["status"] == "in_progress"
    assert data["session_id"] == session.session_id


def test_session_load(tmp_path):
    tracker = SessionTracker(str(tmp_path))
    original = tracker.start("My task")
    tracker2 = SessionTracker(str(tmp_path))
    loaded = tracker2.load()
    assert loaded is not None
    assert loaded.session_id == original.session_id
    assert loaded.task == "My task"


def test_delegation_lifecycle(tmp_path):
    tracker = SessionTracker(str(tmp_path))
    tracker.start("Parent task")
    tracker.start_delegation("d1", "coder", "Write code")
    assert tracker._session.delegations[0].status == "in_progress"
    tracker.complete_delegation("d1", "Code written")
    assert tracker._session.delegations[0].status == "completed"
    assert tracker._session.delegations[0].summary == "Code written"


def test_fail_delegation(tmp_path):
    tracker = SessionTracker(str(tmp_path))
    tracker.start("Parent task")
    tracker.start_delegation("d1", "coder", "Write code")
    tracker.fail_delegation("d1", "Syntax error")
    assert tracker._session.delegations[0].status == "failed"
    assert tracker._session.delegations[0].summary == "Syntax error"


def test_interrupted_delegations(tmp_path):
    tracker = SessionTracker(str(tmp_path))
    tracker.start("Parent task")
    tracker.start_delegation("d1", "coder", "Task A")
    tracker.start_delegation("d2", "tester", "Task B")
    tracker.complete_delegation("d1", "Done")
    interrupted = tracker.get_interrupted_delegations()
    assert len(interrupted) == 1
    assert interrupted[0].id == "d2"


def test_complete_session(tmp_path):
    tracker = SessionTracker(str(tmp_path))
    tracker.start("My task")
    session_id = tracker._session.session_id
    tracker.complete_session()
    assert not (tmp_path / ".kadmon" / "session.json").exists()
    archived = tmp_path / ".kadmon" / "sessions" / f"{session_id}.json"
    assert archived.exists()
    data = json.loads(archived.read_text())
    assert data["status"] == "completed"


def test_mark_handed_off(tmp_path):
    tracker = SessionTracker(str(tmp_path))
    tracker.start("My task")
    session_id = tracker._session.session_id
    tracker.mark_handed_off()
    assert not (tmp_path / ".kadmon" / "session.json").exists()
    archived = tmp_path / ".kadmon" / "sessions" / f"{session_id}.json"
    assert archived.exists()
    data = json.loads(archived.read_text())
    assert data["status"] == "handed_off"


def test_load_no_session(tmp_path):
    tracker = SessionTracker(str(tmp_path))
    assert tracker.load() is None
