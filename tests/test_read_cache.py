from kadmon.memory.read_cache import ReadCache
from kadmon.tools.file_io import EditFileTool, ReadFileTool, WriteFileTool


def test_read_cache_dedup_on_second_read(tmp_path):
    (tmp_path / "f.txt").write_text("hello\nworld\n")
    cache = ReadCache()
    tool = ReadFileTool(str(tmp_path), read_cache=cache)

    r1 = tool.execute(path="f.txt")
    assert "hello" in r1.output

    r2 = tool.execute(path="f.txt")
    assert "unchanged" in r2.output
    assert "12 bytes" in r2.output
    assert "2 lines" in r2.output


def test_read_cache_no_dedup_on_range_read(tmp_path):
    (tmp_path / "f.txt").write_text("a\nb\nc\n")
    cache = ReadCache()
    tool = ReadFileTool(str(tmp_path), read_cache=cache)

    tool.execute(path="f.txt")
    r2 = tool.execute(path="f.txt", start_line=1, end_line=2)
    assert "unchanged" not in r2.output
    assert "1 | a" in r2.output


def test_read_cache_invalidated_by_write(tmp_path):
    (tmp_path / "f.txt").write_text("original")
    cache = ReadCache()
    read_tool = ReadFileTool(str(tmp_path), read_cache=cache)
    write_tool = WriteFileTool(str(tmp_path), read_cache=cache)

    read_tool.execute(path="f.txt")
    write_tool.execute(path="f.txt", content="changed")

    r = read_tool.execute(path="f.txt")
    assert "unchanged" not in r.output
    assert "changed" in r.output


def test_read_cache_invalidated_by_edit(tmp_path):
    (tmp_path / "f.txt").write_text("foo bar")
    cache = ReadCache()
    read_tool = ReadFileTool(str(tmp_path), read_cache=cache)
    edit_tool = EditFileTool(str(tmp_path), read_cache=cache)

    read_tool.execute(path="f.txt")
    edit_tool.execute(path="f.txt", old_str="foo", new_str="baz")

    r = read_tool.execute(path="f.txt")
    assert "unchanged" not in r.output
    assert "baz" in r.output


def test_read_cache_detects_external_change(tmp_path):
    (tmp_path / "f.txt").write_text("v1")
    cache = ReadCache()
    tool = ReadFileTool(str(tmp_path), read_cache=cache)

    tool.execute(path="f.txt")
    (tmp_path / "f.txt").write_text("v2")

    r = tool.execute(path="f.txt")
    assert "unchanged" not in r.output
    assert "v2" in r.output


def test_read_cache_none_backward_compat(tmp_path):
    (tmp_path / "f.txt").write_text("data\n")
    tool = ReadFileTool(str(tmp_path))

    r1 = tool.execute(path="f.txt")
    r2 = tool.execute(path="f.txt")
    assert "data" in r1.output
    assert "data" in r2.output
    assert "unchanged" not in r2.output
