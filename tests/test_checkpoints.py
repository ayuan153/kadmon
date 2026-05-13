"""Tests for Checkpoints & Rewind feature."""


from kadmon.checkpoints import CheckpointManager
from kadmon.tools.checkpoint import CheckpointRollbackTool
from kadmon.tools.file_io import WriteFileTool, EditFileTool
from kadmon.conversation import ConversationHistory


# --- CheckpointManager tests ---


def test_checkpoint_create(tmp_path):
    (tmp_path / "a.py").write_text("hello")
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=5)
    cid = mgr.create(["a.py"], tool="write_file")
    assert cid != ""
    entries = mgr.list()
    assert len(entries) == 1
    assert entries[0]["id"] == cid
    assert entries[0]["tool"] == "write_file"
    assert "a.py" in entries[0]["files"]


def test_checkpoint_rollback(tmp_path):
    (tmp_path / "a.py").write_text("original")
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=5)
    cid = mgr.create(["a.py"], tool="write_file")
    (tmp_path / "a.py").write_text("modified")
    restored = mgr.rollback(cid)
    assert "a.py" in restored
    assert (tmp_path / "a.py").read_text() == "original"


def test_checkpoint_rollback_latest(tmp_path):
    (tmp_path / "a.py").write_text("v1")
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=5)
    mgr.create(["a.py"], tool="write_file")
    (tmp_path / "a.py").write_text("v2")
    mgr.create(["a.py"], tool="write_file")
    (tmp_path / "a.py").write_text("v3")
    restored = mgr.rollback()
    assert "a.py" in restored
    assert (tmp_path / "a.py").read_text() == "v2"


def test_checkpoint_no_existing_file(tmp_path):
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=5)
    cid = mgr.create(["nonexistent.py"], tool="write_file")
    assert cid == ""


def test_checkpoint_prune(tmp_path):
    max_cp = 3
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=max_cp)
    for i in range(max_cp + 1):
        (tmp_path / "a.py").write_text(f"v{i}")
        mgr.create(["a.py"], tool="write_file")
    assert len(mgr.list()) == max_cp


def test_checkpoint_clear(tmp_path):
    (tmp_path / "a.py").write_text("x")
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=5)
    mgr.create(["a.py"], tool="write_file")
    mgr.create(["a.py"], tool="write_file")
    mgr.clear()
    assert mgr.list() == []


def test_checkpoint_list(tmp_path):
    (tmp_path / "a.py").write_text("x")
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=5)
    id1 = mgr.create(["a.py"], tool="tool1")
    (tmp_path / "a.py").write_text("y")
    id2 = mgr.create(["a.py"], tool="tool2")
    entries = mgr.list()
    assert len(entries) == 2
    assert entries[0]["id"] == id2  # newest first
    assert entries[1]["id"] == id1


# --- CheckpointRollbackTool tests ---


def test_rollback_tool(tmp_path):
    (tmp_path / "a.py").write_text("original")
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=5)
    cid = mgr.create(["a.py"], tool="write_file")
    (tmp_path / "a.py").write_text("changed")
    tool = CheckpointRollbackTool(mgr)
    result = tool.execute(checkpoint_id=cid)
    assert not result.error
    assert (tmp_path / "a.py").read_text() == "original"


def test_rollback_tool_empty(tmp_path):
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=5)
    tool = CheckpointRollbackTool(mgr)
    result = tool.execute()
    assert result.error


# --- File tool integration tests ---


def test_write_file_creates_checkpoint(tmp_path):
    (tmp_path / "foo.py").write_text("original")
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=5)
    tool = WriteFileTool(str(tmp_path), checkpoint_manager=mgr)
    tool.execute(path="foo.py", content="new content")
    assert len(mgr.list()) == 1
    mgr.rollback()
    assert (tmp_path / "foo.py").read_text() == "original"


def test_edit_file_creates_checkpoint(tmp_path):
    (tmp_path / "bar.py").write_text("line1\nline2\nline3")
    mgr = CheckpointManager(str(tmp_path), max_checkpoints=5)
    tool = EditFileTool(str(tmp_path), checkpoint_manager=mgr)
    tool.execute(path="bar.py", old_str="line2", new_str="replaced")
    assert len(mgr.list()) == 1
    mgr.rollback()
    assert (tmp_path / "bar.py").read_text() == "line1\nline2\nline3"


# --- ConversationHistory tests ---


def test_conversation_snapshot(tmp_path):
    hist = ConversationHistory(str(tmp_path), max_turns=10)
    tid = hist.snapshot("fix bug", context=[{"role": "user"}])
    assert isinstance(tid, int)
    turns = hist.list_turns()
    assert len(turns) == 1
    assert turns[0]["prompt"] == "fix bug"


def test_conversation_list_turns(tmp_path):
    hist = ConversationHistory(str(tmp_path), max_turns=10)
    hist.snapshot("first", context=[])
    hist.snapshot("second", context=[])
    turns = hist.list_turns()
    assert len(turns) == 2
    assert turns[0]["prompt"] == "second"  # newest first
    assert turns[1]["prompt"] == "first"


def test_conversation_rewind(tmp_path):
    hist = ConversationHistory(str(tmp_path), max_turns=10)
    t1 = hist.snapshot("first", context=[])
    hist.snapshot("second", context=[])
    hist.snapshot("third", context=[])
    turn = hist.rewind(t1)
    assert turn is not None
    assert turn.prompt == "first"
    assert len(hist.list_turns()) == 1


def test_conversation_rewind_nonexistent(tmp_path):
    hist = ConversationHistory(str(tmp_path), max_turns=10)
    hist.snapshot("first", context=[])
    result = hist.rewind(999)
    assert result is None


def test_conversation_prune(tmp_path):
    max_turns = 3
    hist = ConversationHistory(str(tmp_path), max_turns=max_turns)
    for i in range(max_turns + 1):
        hist.snapshot(f"turn {i}", context=[])
    assert len(hist.list_turns()) == max_turns
