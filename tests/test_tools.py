import subprocess

from kadmon.tools.base import ToolRegistry
from kadmon.tools.file_io import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from kadmon.tools.search import GrepSearchTool
from kadmon.tools.shell import ShellTool
from kadmon.tools.submit import SubmitTool


def test_read_file(tmp_path):
    (tmp_path / "hello.txt").write_text("line1\nline2\nline3\n")
    tool = ReadFileTool(str(tmp_path))
    result = tool.execute(path="hello.txt")
    assert not result.error
    assert "1 | line1" in result.output
    assert "3 | line3" in result.output


def test_read_file_not_found(tmp_path):
    tool = ReadFileTool(str(tmp_path))
    result = tool.execute(path="nope.txt")
    assert result.error
    assert "not found" in result.output.lower()


def test_write_file(tmp_path):
    tool = WriteFileTool(str(tmp_path))
    result = tool.execute(path="sub/out.txt", content="hello world")
    assert not result.error
    assert (tmp_path / "sub" / "out.txt").read_text() == "hello world"


def test_edit_file(tmp_path):
    (tmp_path / "f.txt").write_text("foo bar baz")
    tool = EditFileTool(str(tmp_path))
    result = tool.execute(path="f.txt", old_str="bar", new_str="qux")
    assert not result.error
    assert (tmp_path / "f.txt").read_text() == "foo qux baz"


def test_edit_file_no_match(tmp_path):
    (tmp_path / "f.txt").write_text("foo bar")
    tool = EditFileTool(str(tmp_path))
    result = tool.execute(path="f.txt", old_str="xyz", new_str="abc")
    assert result.error
    assert "not found" in result.output.lower()


def test_edit_file_multiple_matches(tmp_path):
    (tmp_path / "f.txt").write_text("aaa\naaa\n")
    tool = EditFileTool(str(tmp_path))
    result = tool.execute(path="f.txt", old_str="aaa", new_str="bbb")
    assert result.error
    assert "2 times" in result.output


def test_list_dir(tmp_path):
    (tmp_path / "a.py").touch()
    (tmp_path / "b.txt").touch()
    tool = ListDirTool(str(tmp_path))
    result = tool.execute(path=".")
    assert not result.error
    assert "a.py" in result.output
    assert "b.txt" in result.output


def test_grep_search(tmp_path):
    (tmp_path / "code.py").write_text("def hello():\n    pass\n")
    (tmp_path / "other.py").write_text("x = 1\n")
    tool = GrepSearchTool(str(tmp_path))
    result = tool.execute(pattern="hello")
    assert not result.error
    assert "hello" in result.output


def test_shell(tmp_path):
    tool = ShellTool(str(tmp_path))
    result = tool.execute(command="echo hello")
    assert not result.error
    assert "hello" in result.output


def test_shell_timeout(tmp_path, monkeypatch):
    tool = ShellTool(str(tmp_path))
    # Patch timeout to 1s
    original_run = subprocess.run

    def patched_run(*args, **kwargs):
        kwargs['timeout'] = 1
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, 'run', patched_run)
    result = tool.execute(command="sleep 10")
    assert result.error
    assert "timed out" in result.output.lower()


def test_submit_empty(tmp_path):
    # Initialize a git repo with a commit so git diff works
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    (tmp_path / "f.txt").write_text("init")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    tool = SubmitTool(str(tmp_path))
    result = tool.execute()
    assert result.error
    assert "no changes" in result.output.lower()


def test_tool_registry(tmp_path):
    registry = ToolRegistry()
    tool = ReadFileTool(str(tmp_path))
    registry.register(tool)

    assert len(registry.definitions()) == 1
    assert registry.definitions()[0]['name'] == 'read_file'

    (tmp_path / "x.txt").write_text("content")
    result = registry.execute('read_file', path="x.txt")
    assert not result.error
    assert "content" in result.output

    result = registry.execute('nonexistent')
    assert result.error


def test_path_escape(tmp_path):
    tool = ReadFileTool(str(tmp_path))
    result = tool.execute(path="../../../etc/passwd")
    assert result.error
    assert "escapes" in result.output.lower() or "not found" in result.output.lower()
