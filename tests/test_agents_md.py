"""Tests for AGENTS.md ingestion feature."""

import hashlib

from kadmon.agent.loop import AgentLoop
from kadmon.memory.librarian import Librarian
from kadmon.providers.base import LLMResponse, TokenUsage
from kadmon.tools.base import ToolRegistry


class MockProvider:
    def __init__(self, response: str = "merged content"):
        self._response = response
        self.call_count = 0

    def complete(self, messages, tools=None, system=""):
        self.call_count += 1
        return LLMResponse(content=self._response, usage=TokenUsage(input_tokens=10, output_tokens=10))


def _make_agent(tmp_path):
    provider = MockProvider()
    registry = ToolRegistry()
    librarian = Librarian(str(tmp_path))
    agent = AgentLoop(provider=provider, tools=registry, librarian=librarian, repo_root=str(tmp_path))
    return agent, provider


def test_ingest_agents_md_no_file(tmp_path):
    agent, provider = _make_agent(tmp_path)
    agent._ingest_agents_md()
    assert provider.call_count == 0


def test_ingest_agents_md_first_time(tmp_path):
    content = "# AGENTS\n\nSome rules here."
    (tmp_path / "AGENTS.md").write_text(content)

    agent, provider = _make_agent(tmp_path)
    agent._ingest_agents_md()

    expected_hash = hashlib.sha256(content.encode()).hexdigest()
    hash_path = tmp_path / ".kadmon" / "agents_md_hash"

    assert provider.call_count > 0
    assert hash_path.exists()
    assert hash_path.read_text().strip() == expected_hash
    assert (tmp_path / ".kadmon" / "library").is_dir()


def test_ingest_agents_md_unchanged(tmp_path):
    content = "# AGENTS\n\nSome rules here."
    (tmp_path / "AGENTS.md").write_text(content)
    expected_hash = hashlib.sha256(content.encode()).hexdigest()

    kadmon_dir = tmp_path / ".kadmon"
    kadmon_dir.mkdir(parents=True)
    (kadmon_dir / "agents_md_hash").write_text(expected_hash)

    agent, provider = _make_agent(tmp_path)
    agent._ingest_agents_md()

    assert provider.call_count == 0


def test_ingest_agents_md_changed(tmp_path):
    new_content = "# AGENTS\n\nUpdated rules."
    (tmp_path / "AGENTS.md").write_text(new_content)

    kadmon_dir = tmp_path / ".kadmon"
    kadmon_dir.mkdir(parents=True)
    (kadmon_dir / "agents_md_hash").write_text("oldhashvalue")

    agent, provider = _make_agent(tmp_path)
    agent._ingest_agents_md()

    expected_hash = hashlib.sha256(new_content.encode()).hexdigest()
    hash_path = kadmon_dir / "agents_md_hash"

    assert provider.call_count > 0
    assert hash_path.read_text().strip() == expected_hash
    assert (tmp_path / ".kadmon" / "library").is_dir()


def test_ingest_agents_md_creates_kadmon_dir(tmp_path):
    content = "# AGENTS\n\nRules."
    (tmp_path / "AGENTS.md").write_text(content)
    assert not (tmp_path / ".kadmon").exists()

    agent, provider = _make_agent(tmp_path)
    agent._ingest_agents_md()

    assert (tmp_path / ".kadmon").is_dir()
    assert (tmp_path / ".kadmon" / "agents_md_hash").exists()
