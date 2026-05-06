from kadmon.tools.skeleton import FileSkeletonTool


def test_skeleton_basic(tmp_path):
    src = tmp_path / "example.py"
    src.write_text(
        "class Foo:\n"
        "    def bar(self, x: int) -> str:\n"
        "        return helper(x)\n"
        "\n"
        "def helper(x):\n"
        "    return str(x)\n"
    )
    tool = FileSkeletonTool(str(tmp_path))
    result = tool.execute(path="example.py")
    assert not result.error
    assert "class Foo" in result.output
    assert "def bar(self, x: int) -> str" in result.output
    assert "def helper(x)" in result.output
    assert "→ calls: helper" in result.output


def test_skeleton_path_escape(tmp_path):
    tool = FileSkeletonTool(str(tmp_path))
    result = tool.execute(path="../../etc/passwd")
    assert result.error
    assert "escapes" in result.output


def test_skeleton_not_found(tmp_path):
    tool = FileSkeletonTool(str(tmp_path))
    result = tool.execute(path="nope.py")
    assert result.error
    assert "not found" in result.output.lower()


def test_skeleton_fallback(tmp_path):
    # .xyz extension won't be parsed by tree-sitter, triggers fallback
    src = tmp_path / "example.xyz"
    src.write_text("def hello():\n    pass\n")
    tool = FileSkeletonTool(str(tmp_path))
    result = tool.execute(path="example.xyz")
    assert not result.error
    assert "fallback" in result.output
    assert "def hello()" in result.output
