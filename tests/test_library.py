"""Tests for kadmon Library Team (Phase 1): IndexAgent, ReadAgent, WriteAgent, and Library tools."""

from kadmon.providers.base import LLMResponse, TokenUsage
from kadmon.memory.agents.index_agent import IndexAgent
from kadmon.memory.agents.read_agent import ReadAgent
from kadmon.memory.agents.write_agent import WriteAgent
from kadmon.tools.library import LibraryReadTool, LibraryWriteTool, LibraryStatusTool


class MockProvider:
    def __init__(self, response: str):
        self._response = response

    def complete(self, messages, tools=None, system=""):
        return LLMResponse(content=self._response, usage=TokenUsage(input_tokens=100, output_tokens=50))


# === IndexAgent Tests ===


def test_index_agent_finds_relevant_files(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "index.md").write_text("# Library Index\n\n- conventions.md\n")
    (lib / "conventions.md").write_text("# Conventions\n\nUse pytest for testing.\n")

    provider = MockProvider("FILES: conventions.md\nORTHOGONAL: false")
    agent = IndexAgent(provider, lib)
    result = agent.find_relevant("how do we test?")

    assert result.files == ["conventions.md"]
    assert result.orthogonal is False


def test_index_agent_empty_library(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()

    provider = MockProvider("FILES: none\nORTHOGONAL: false")
    agent = IndexAgent(provider, lib)
    result = agent.find_relevant("anything")

    assert result.files == []
    assert result.orthogonal is False


def test_index_agent_orthogonal_detection(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "index.md").write_text("# Library Index\n\n- conventions.md\n")
    (lib / "conventions.md").write_text("# Conventions\n")

    provider = MockProvider("FILES: conventions.md\nORTHOGONAL: true")
    agent = IndexAgent(provider, lib)
    result = agent.find_relevant("unrelated task")

    assert result.orthogonal is True


def test_index_agent_no_relevant_files(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "index.md").write_text("# Library Index\n\n- conventions.md\n")
    (lib / "conventions.md").write_text("# Conventions\n")

    provider = MockProvider("FILES: none\nORTHOGONAL: false")
    agent = IndexAgent(provider, lib)
    result = agent.find_relevant("something irrelevant")

    assert result.files == []


# === ReadAgent Tests ===


def test_read_agent_synthesizes(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "conventions.md").write_text("# Conventions\n\nUse pytest.\n")

    provider = MockProvider("Use pytest for all testing.")
    agent = ReadAgent(provider, lib)
    result = agent.synthesize(["conventions.md"], "how to test?")

    assert result == "Use pytest for all testing."


def test_read_agent_missing_files(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()

    provider = MockProvider("should not be called")
    agent = ReadAgent(provider, lib)
    result = agent.synthesize(["nonexistent.md"], "anything")

    assert result == "No relevant library context found."


# === WriteAgent Tests ===


def test_write_agent_creates_new_file(tmp_path):
    lib = tmp_path / "library"

    provider = MockProvider("# Conventions\n\n- Use pytest\n\nLast Updated: 2026-05-11")
    agent = WriteAgent(provider, lib)
    result = agent.update("conventions", "Use pytest")

    assert result == "Updated library: conventions.md"
    assert (lib / "conventions.md").exists()
    assert "Use pytest" in (lib / "conventions.md").read_text()


def test_write_agent_updates_existing(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "conventions.md").write_text("# Conventions\n\n- Use black\n")

    provider = MockProvider("# Conventions\n\n- Use black\n- Use pytest\n\nLast Updated: 2026-05-11")
    agent = WriteAgent(provider, lib)
    agent.update("conventions", "Use pytest")

    content = (lib / "conventions.md").read_text()
    assert "Use black" in content
    assert "Use pytest" in content


def test_write_agent_updates_index(tmp_path):
    lib = tmp_path / "library"

    provider = MockProvider("# Architecture\n\nModular design.")
    agent = WriteAgent(provider, lib)
    agent.update("architecture", "Modular design")

    index = (lib / "index.md").read_text()
    assert "architecture.md" in index


# === LibraryReadTool Tests ===


def test_library_read_tool_happy_path(tmp_path):
    lib = tmp_path / ".kadmon" / "library"
    lib.mkdir(parents=True)
    (lib / "index.md").write_text("# Library Index\n\n- conventions.md\n")
    (lib / "conventions.md").write_text("# Conventions\n\nUse pytest.\n")

    class MultiProvider:
        def __init__(self):
            self._calls = 0

        def complete(self, messages, tools=None, system=""):
            self._calls += 1
            if self._calls == 1:
                content = "FILES: conventions.md\nORTHOGONAL: false"
            else:
                content = "Synthesized: use pytest for testing."
            return LLMResponse(content=content, usage=TokenUsage(input_tokens=100, output_tokens=50))

    tool = LibraryReadTool(MultiProvider(), str(tmp_path))
    result = tool.execute(query="how to test?")

    assert result.output == "Synthesized: use pytest for testing."
    assert result.error is False


def test_library_read_tool_empty_library(tmp_path):
    provider = MockProvider("FILES: none\nORTHOGONAL: false")
    tool = LibraryReadTool(provider, str(tmp_path))
    result = tool.execute(query="anything")

    assert result.output == "No relevant library context found."


# === LibraryWriteTool Tests ===


def test_library_write_tool(tmp_path):
    provider = MockProvider("# Conventions\n\n- Use pytest\n\nLast Updated: 2026-05-11")
    tool = LibraryWriteTool(provider, str(tmp_path))
    result = tool.execute(topic="conventions", content="Use pytest")

    assert "Updated library:" in result.output
    assert (tmp_path / ".kadmon" / "library" / "conventions.md").exists()


# === LibraryStatusTool Tests ===


def test_library_status_tool_with_files(tmp_path):
    lib = tmp_path / ".kadmon" / "library"
    lib.mkdir(parents=True)
    (lib / "index.md").write_text("# Library Index\n\n- conventions.md\n")
    (lib / "conventions.md").write_text("# Conventions\n\nUse pytest.\n")

    tool = LibraryStatusTool(str(tmp_path))
    result = tool.execute()

    assert "conventions.md" in result.output
    assert "Library is empty." not in result.output


def test_library_status_tool_empty(tmp_path):
    tool = LibraryStatusTool(str(tmp_path))
    result = tool.execute()

    assert result.output == "Library is empty."
