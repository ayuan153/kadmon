"""Tests for Phase 3: TokenTracker, LibraryCache, token tracking in agents, caching in LibraryReadTool."""

from kadmon.memory.library_cache import LibraryCache
from kadmon.memory.token_tracker import TokenTracker
from kadmon.memory.agents.index_agent import IndexAgent
from kadmon.memory.agents.read_agent import ReadAgent
from kadmon.memory.agents.write_agent import WriteAgent
from kadmon.providers.base import LLMResponse, TokenUsage
from kadmon.tools.library import LibraryReadTool, LibraryStatusTool


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


# --- TokenTracker tests ---


def test_token_tracker_record():
    t = TokenTracker()
    t.record(100, 50)
    t.record(200, 80)
    assert t.input_tokens == 300
    assert t.output_tokens == 130
    assert t.call_count == 2
    assert t.total_tokens == 430


def test_token_tracker_summary():
    t = TokenTracker()
    t.record(100, 50)
    t.record(200, 80)
    s = t.summary()
    assert "2 calls" in s
    assert "430 tokens" in s
    assert "300 in" in s
    assert "130 out" in s


# --- LibraryCache tests ---


def test_library_cache_hit():
    c = LibraryCache()
    c.set("how to deploy", "use kubectl apply")
    assert c.get("how to deploy") == "use kubectl apply"


def test_library_cache_miss():
    c = LibraryCache()
    assert c.get("unknown query") is None


def test_library_cache_clear():
    c = LibraryCache()
    c.set("q1", "r1")
    c.clear()
    assert c.get("q1") is None


# --- Agent token tracking tests ---


def test_index_agent_tracks_tokens(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "index.md").write_text("- conventions.md\n")
    (lib / "conventions.md").write_text("# Conventions\nUse black formatter.\n")

    provider = MockProvider("FILES: conventions.md\nORTHOGONAL: false")
    agent = IndexAgent(provider, lib)
    tracker = TokenTracker()
    agent.find_relevant("formatting rules", tracker=tracker)
    assert tracker.call_count == 1
    assert tracker.input_tokens == 100
    assert tracker.output_tokens == 50


def test_read_agent_tracks_tokens(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "conventions.md").write_text("# Conventions\nUse black.\n")

    provider = MockProvider("Use black for formatting.")
    agent = ReadAgent(provider, lib)
    tracker = TokenTracker()
    agent.synthesize(["conventions.md"], "formatting", tracker=tracker)
    assert tracker.call_count == 1
    assert tracker.total_tokens == 150


def test_write_agent_tracks_tokens(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()

    provider = MockProvider("# Architecture\nMicroservices.\n\nLast Updated: 2026-05-11")
    agent = WriteAgent(provider, lib)
    tracker = TokenTracker()
    agent.update("architecture", "We use microservices", tracker=tracker)
    assert tracker.call_count == 1
    assert tracker.total_tokens == 150


# --- LibraryReadTool caching tests ---


def test_library_read_caches_result(tmp_path):
    lib = tmp_path / ".kadmon" / "library"
    lib.mkdir(parents=True)
    (lib / "index.md").write_text("- conventions.md\n")
    (lib / "conventions.md").write_text("# Conventions\nUse black.\n")

    provider = MultiMockProvider([
        "FILES: conventions.md\nORTHOGONAL: false",
        "Use black for formatting.",
    ])
    tool = LibraryReadTool(provider, str(tmp_path))
    r1 = tool.execute("formatting")
    count_after_first = tool.tracker.call_count
    r2 = tool.execute("formatting")
    assert r2.output == r1.output
    assert tool.tracker.call_count == count_after_first


def test_library_read_different_queries_not_cached(tmp_path):
    lib = tmp_path / ".kadmon" / "library"
    lib.mkdir(parents=True)
    (lib / "index.md").write_text("- conventions.md\n")
    (lib / "conventions.md").write_text("# Conventions\nUse black.\n")

    provider = MultiMockProvider([
        "FILES: conventions.md\nORTHOGONAL: false",
        "Answer about formatting.",
        "FILES: conventions.md\nORTHOGONAL: false",
        "Answer about testing.",
    ])
    tool = LibraryReadTool(provider, str(tmp_path))
    tool.execute("formatting")
    count_after_first = tool.tracker.call_count
    tool.execute("testing")
    assert tool.tracker.call_count > count_after_first


# --- LibraryStatusTool token usage display ---


def test_library_status_shows_token_usage(tmp_path):
    lib = tmp_path / ".kadmon" / "library"
    lib.mkdir(parents=True)
    (lib / "index.md").write_text("- conventions.md\n")
    (lib / "conventions.md").write_text("# Conventions\n")

    read_tracker = TokenTracker()
    read_tracker.record(500, 200)
    write_tracker = TokenTracker()
    write_tracker.record(300, 100)

    tool = LibraryStatusTool(str(tmp_path), read_tracker=read_tracker, write_tracker=write_tracker)
    result = tool.execute()
    assert "Token usage" in result.output
    assert "Read:" in result.output
    assert "Write:" in result.output
    assert "700 tokens" in result.output
    assert "400 tokens" in result.output
