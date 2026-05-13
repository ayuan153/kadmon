"""P0 tests for path-scoped rules and parallel workers."""
from __future__ import annotations

from pathlib import Path


from kadmon.memory.agents.index_agent import IndexAgent
from kadmon.providers.base import LLMResponse, TokenUsage
from kadmon.tools.parallel import ParallelDispatchTool
from kadmon.workers import WorkerResult


class MockProvider:
    def __init__(self, response: str = "FILES: none\nORTHOGONAL: false"):
        self._response = response

    def complete(self, messages, tools=None, system=""):
        return LLMResponse(content=self._response, usage=TokenUsage(input_tokens=10, output_tokens=10))


# --- Path-Scoped Rules ---


class TestMatchesScope:
    def setup_method(self):
        self.agent = IndexAgent(MockProvider(), Path("/tmp/lib"))

    def test_matches_scope_basic(self):
        assert self.agent._matches_scope("src/auth/**", ["src/auth/login.py"])

    def test_matches_scope_no_match(self):
        assert not self.agent._matches_scope("src/auth/**", ["src/db/models.py"])

    def test_matches_scope_multiple_patterns(self):
        assert self.agent._matches_scope("src/auth/**, tests/test_auth*", ["tests/test_auth_login.py"])


class TestIndexAgentFileHeaders:
    def _setup_library(self, tmp_path):
        lib = tmp_path / ".kadmon" / "library"
        lib.mkdir(parents=True)

        (lib / "auth.md").write_text("# Auth Patterns\nScope: src/auth/**\n\n## Summary\nAuth stuff\n")
        (lib / "conventions.md").write_text("# Conventions\n\n## Summary\nGeneral conventions\n")
        (lib / "index.md").write_text("- auth.md\n- conventions.md\n")

        return lib

    def test_index_agent_filters_scoped_files(self, tmp_path):
        lib = self._setup_library(tmp_path)
        agent = IndexAgent(MockProvider(), lib)
        headers = agent._read_file_headers((lib / "index.md").read_text(), active_files=["src/db/models.py"])
        assert "auth.md" not in headers
        assert "conventions.md" in headers

    def test_index_agent_includes_unscoped(self, tmp_path):
        lib = self._setup_library(tmp_path)
        agent = IndexAgent(MockProvider(), lib)
        headers = agent._read_file_headers((lib / "index.md").read_text(), active_files=["src/db/models.py"])
        assert "conventions.md" in headers

    def test_index_agent_includes_matching_scope(self, tmp_path):
        lib = self._setup_library(tmp_path)
        agent = IndexAgent(MockProvider(), lib)
        headers = agent._read_file_headers((lib / "index.md").read_text(), active_files=["src/auth/login.py"])
        assert "auth.md" in headers
        assert "conventions.md" in headers

    def test_index_agent_no_active_files_includes_all(self, tmp_path):
        lib = self._setup_library(tmp_path)
        agent = IndexAgent(MockProvider(), lib)
        headers = agent._read_file_headers((lib / "index.md").read_text(), active_files=None)
        assert "auth.md" in headers
        assert "conventions.md" in headers


# --- Parallel Workers ---


def test_parallel_dispatch_empty_tasks():
    tool = ParallelDispatchTool(MockProvider(), "/tmp")
    result = tool.execute(tasks=[])
    assert result.error
    assert "at least one task" in result.output


def test_parallel_dispatch_too_many_tasks():
    tool = ParallelDispatchTool(MockProvider(), "/tmp")
    result = tool.execute(tasks=["t1", "t2", "t3", "t4", "t5", "t6"])
    assert result.error
    assert "max 5" in result.output


def test_worker_result_dataclass():
    r = WorkerResult(task="fix bug", output="done", success=True, files_modified=["a.py"])
    assert r.task == "fix bug"
    assert r.output == "done"
    assert r.success is True
    assert r.files_modified == ["a.py"]

    r2 = WorkerResult(task="t", output="", success=False)
    assert r2.files_modified == []
