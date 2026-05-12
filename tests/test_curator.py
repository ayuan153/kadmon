"""Tests for CuratorAgent."""


from kadmon.memory.agents.curator_agent import CuratorAgent
from kadmon.memory.session_log import SessionLogger
from kadmon.providers.base import LLMResponse, TokenUsage


class MockProvider:
    def __init__(self, response: str):
        self._response = response

    def complete(self, messages, tools=None, system=""):
        return LLMResponse(content=self._response, usage=TokenUsage(input_tokens=100, output_tokens=50))


class MultiMockProvider:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self._idx = 0

    def complete(self, messages, tools=None, system=""):
        resp = self._responses[self._idx]
        self._idx += 1
        return LLMResponse(content=resp, usage=TokenUsage(input_tokens=100, output_tokens=50))


def _setup_library(tmp_path):
    """Create minimal .kadmon/library/index.md so prune agent doesn't crash."""
    lib = tmp_path / ".kadmon" / "library"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "index.md").write_text("# Library Index\n")
    sessions = lib / "sessions"
    sessions.mkdir(exist_ok=True)


def _log_path(tmp_path):
    return tmp_path / ".kadmon" / "sessions" / "log.jsonl"


def test_curate_empty_log(tmp_path):
    _setup_library(tmp_path)
    provider = MockProvider("NOTHING")
    agent = CuratorAgent(provider, str(tmp_path))
    result = agent.curate()
    assert result == "No session log to curate."


def test_curate_nothing_worth_preserving(tmp_path):
    _setup_library(tmp_path)
    logger = SessionLogger(str(tmp_path))
    logger.session_start("fix auth bug")
    logger.tool_executed("read_file", {"path": "src/auth.py"}, True)
    logger.session_end("completed")

    provider = MockProvider("NOTHING")
    agent = CuratorAgent(provider, str(tmp_path))
    result = agent.curate()
    assert result == "Session curated — nothing worth preserving."
    assert not _log_path(tmp_path).exists()


def test_curate_extracts_learnings(tmp_path):
    _setup_library(tmp_path)
    logger = SessionLogger(str(tmp_path))
    logger.session_start("fix auth bug")
    logger.tool_executed("read_file", {"path": "src/auth.py"}, True)
    logger.session_end("completed")

    provider = MultiMockProvider([
        "TOPIC: conventions\nCONTENT: Use pytest for testing",
        "# Conventions\n\n- Use pytest\n\nLast Updated: 2026-05-12",
        "ARCHIVE: fix-auth.md\nREMOVE: none\nKEEP: conventions.md",
    ])
    agent = CuratorAgent(provider, str(tmp_path))
    result = agent.curate()
    assert "1 learning(s) saved to library" in result
    assert not _log_path(tmp_path).exists()


def test_parse_learnings_single(tmp_path):
    _setup_library(tmp_path)
    provider = MockProvider("")
    agent = CuratorAgent(provider, str(tmp_path))
    result = agent._parse_learnings("TOPIC: conventions\nCONTENT: Use pytest for testing")
    assert result == [("conventions", "Use pytest for testing")]


def test_parse_learnings_multiple(tmp_path):
    _setup_library(tmp_path)
    provider = MockProvider("")
    agent = CuratorAgent(provider, str(tmp_path))
    content = "TOPIC: conventions\nCONTENT: Use pytest\n\nTOPIC: architecture\nCONTENT: Modular design"
    result = agent._parse_learnings(content)
    assert result == [("conventions", "Use pytest"), ("architecture", "Modular design")]


def test_parse_learnings_nothing(tmp_path):
    _setup_library(tmp_path)
    provider = MockProvider("")
    agent = CuratorAgent(provider, str(tmp_path))
    result = agent._parse_learnings("NOTHING")
    assert result == []


def test_format_events(tmp_path):
    _setup_library(tmp_path)
    logger = SessionLogger(str(tmp_path))
    logger.session_start("fix auth bug")
    logger.tool_executed("read_file", {"path": "src/auth.py"}, True)
    logger.session_end("completed")

    provider = MockProvider("")
    agent = CuratorAgent(provider, str(tmp_path))
    events = agent._logger.read_events()
    formatted = agent._format_events(events)
    assert "fix auth bug" in formatted
    assert "read_file" in formatted


def test_extract_task(tmp_path):
    _setup_library(tmp_path)
    logger = SessionLogger(str(tmp_path))
    logger.session_start("fix auth bug")
    logger.session_end("completed")

    provider = MockProvider("")
    agent = CuratorAgent(provider, str(tmp_path))
    events = agent._logger.read_events()
    task = agent._extract_task(events)
    assert task == "fix auth bug"


def test_curate_clears_log_after(tmp_path):
    _setup_library(tmp_path)
    logger = SessionLogger(str(tmp_path))
    logger.session_start("refactor models")
    logger.tool_executed("write_file", {"path": "models.py"}, True)
    logger.session_end("completed")

    assert _log_path(tmp_path).exists()

    provider = MockProvider("NOTHING")
    agent = CuratorAgent(provider, str(tmp_path))
    agent.curate()
    assert not _log_path(tmp_path).exists()
