"""Tests for Phase 2: PruneAgent, auto-prune in LibraryReadTool, and CLI continue command."""

from click.testing import CliRunner

from kadmon.cli import main
from kadmon.memory.agents.prune_agent import PruneAgent, PruneResult
from kadmon.providers.base import LLMResponse, TokenUsage


class MockProvider:
    def __init__(self, response: str):
        self._response = response

    def complete(self, messages, tools=None, system=""):
        return LLMResponse(content=self._response, usage=TokenUsage(input_tokens=100, output_tokens=50))


class MultiMockProvider:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def complete(self, messages, tools=None, system=""):
        resp = self._responses.pop(0)
        return LLMResponse(content=resp, usage=TokenUsage(input_tokens=100, output_tokens=50))


def _setup_library(tmp_path, index_content="- conventions.md\n- sessions/current.md\n", session_content="# Current\nWorking on auth fix\n"):
    lib = tmp_path / ".kadmon" / "library"
    lib.mkdir(parents=True)
    (lib / "index.md").write_text(index_content)
    (lib / "conventions.md").write_text("# Conventions\nUse pytest.\n")
    sessions = lib / "sessions"
    sessions.mkdir()
    (sessions / "current.md").write_text(session_content)
    return lib


def test_prune_agent_archives_session(tmp_path):
    lib = _setup_library(tmp_path)
    provider = MockProvider("ARCHIVE: fix-auth-bug.md\nREMOVE: none\nKEEP: conventions.md")
    agent = PruneAgent(provider, lib)

    result = agent.prune("implement login")

    assert result.archived == "fix-auth-bug.md"
    assert not (lib / "sessions" / "current.md").exists()
    assert (lib / "sessions" / "archive" / "fix-auth-bug.md").exists()
    assert (lib / "sessions" / "archive" / "fix-auth-bug.md").read_text() == "# Current\nWorking on auth fix\n"


def test_prune_agent_no_current_session(tmp_path):
    lib = tmp_path / ".kadmon" / "library"
    lib.mkdir(parents=True)
    (lib / "sessions").mkdir()
    # No current.md created
    provider = MockProvider("should not be called")
    agent = PruneAgent(provider, lib)

    result = agent.prune("some task")

    assert result == PruneResult()
    assert result.archived == ""
    assert result.removed == []


def test_prune_agent_removes_stale_files(tmp_path):
    lib = _setup_library(tmp_path, index_content="- conventions.md\n- stale.md\n- sessions/current.md\n")
    (lib / "stale.md").write_text("# Stale content\n")
    provider = MockProvider("ARCHIVE: old-session.md\nREMOVE: stale.md\nKEEP: conventions.md")
    agent = PruneAgent(provider, lib)

    result = agent.prune("new task")

    assert "stale.md" in result.removed
    assert not (lib / "stale.md").exists()
    index = (lib / "index.md").read_text()
    assert "stale.md" not in index
    assert "conventions.md" in index


def test_prune_agent_parse_response(tmp_path):
    lib = tmp_path / ".kadmon" / "library"
    lib.mkdir(parents=True)
    provider = MockProvider("")
    agent = PruneAgent(provider, lib)

    # Standard format
    archive, removed = agent._parse_response("ARCHIVE: my-task.md\nREMOVE: old.md, stale.md\nKEEP: good.md")
    assert archive == "my-task.md"
    assert removed == ["old.md", "stale.md"]

    # No .md extension
    archive, removed = agent._parse_response("ARCHIVE: my-task\nREMOVE: none\nKEEP: all")
    assert archive == "my-task.md"
    assert removed == []

    # Empty archive defaults to session.md
    archive, removed = agent._parse_response("ARCHIVE:\nREMOVE: none")
    assert archive == "session.md"
    assert removed == []

    # Case insensitive
    archive, removed = agent._parse_response("archive: Test.md\nremove: a.md")
    assert archive == "Test.md"
    assert removed == ["a.md"]


def test_library_read_triggers_prune_on_orthogonal(tmp_path):
    from kadmon.tools.library import LibraryReadTool

    lib = _setup_library(tmp_path)
    provider = MultiMockProvider([
        "FILES: conventions.md\nORTHOGONAL: true",
        "ARCHIVE: old-task.md\nREMOVE: none\nKEEP: conventions.md",
        "Here is the synthesized context.",
    ])
    tool = LibraryReadTool(provider, str(tmp_path))

    tool.execute(query="write new feature")

    assert not (lib / "sessions" / "current.md").exists()
    assert (lib / "sessions" / "archive" / "old-task.md").exists()


def test_library_read_no_prune_when_not_orthogonal(tmp_path):
    from kadmon.tools.library import LibraryReadTool

    lib = _setup_library(tmp_path)
    provider = MultiMockProvider([
        "FILES: conventions.md\nORTHOGONAL: false",
        "Here is the synthesized context.",
    ])
    tool = LibraryReadTool(provider, str(tmp_path))

    tool.execute(query="continue auth fix")

    assert (lib / "sessions" / "current.md").exists()


def test_continue_command_no_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["continue"])
    assert result.exit_code != 0
    assert "No saved session" in result.output


def test_continue_command_empty_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".kadmon" / "library" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "current.md").write_text("")
    runner = CliRunner()
    result = runner.invoke(main, ["continue"])
    assert result.exit_code != 0
    assert "No saved session" in result.output
