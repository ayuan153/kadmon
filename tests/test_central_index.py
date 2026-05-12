"""Tests for CentralIndex and the --global status flag."""

import json

import pytest
from click.testing import CliRunner

from kadmon.memory.central_index import CentralIndex, IndexEntry


@pytest.fixture
def index(tmp_path):
    idx = CentralIndex()
    idx._index_dir = tmp_path
    idx._index_path = tmp_path / "index.json"
    return idx


def test_add_entry(index):
    index.add_entry("s1", "/repo/a", "do stuff")
    data = json.loads(index._index_path.read_text())
    assert "s1" in data
    assert data["s1"]["repo"] == "/repo/a"
    assert data["s1"]["task"] == "do stuff"
    assert data["s1"]["status"] == "in_progress"


def test_update_entry(index):
    index.add_entry("s1", "/repo/a", "task")
    index.update_entry("s1", status="completed", files_touched=["f.py"])
    data = json.loads(index._index_path.read_text())
    assert data["s1"]["status"] == "completed"
    assert data["s1"]["files_touched"] == ["f.py"]


def test_update_entry_nonexistent(index):
    index.add_entry("s1", "/repo/a", "task")
    index.update_entry("missing", status="completed")
    data = json.loads(index._index_path.read_text())
    assert "missing" not in data
    assert data["s1"]["status"] == "in_progress"


def test_find_by_repo(index):
    index.add_entry("s1", "/repo/a", "task a")
    index.add_entry("s2", "/repo/b", "task b")
    result = index.find_by_repo("/repo/b")
    assert result is not None
    assert result.session_key == "s2"
    assert result.task == "task b"


def test_find_by_repo_not_found(index):
    index.add_entry("s1", "/repo/a", "task")
    assert index.find_by_repo("/nonexistent") is None


def test_find_by_repo_returns_most_recent(index):
    import json
    entries = {
        "s1": {"session_key": "s1", "repo": "/repo/a", "task": "old task", "started": "2026-05-12T10:00:00Z", "last_updated": "2026-05-12T10:00:00Z", "status": "in_progress", "files_touched": []},
        "s2": {"session_key": "s2", "repo": "/repo/a", "task": "new task", "started": "2026-05-12T11:00:00Z", "last_updated": "2026-05-12T11:00:00Z", "status": "in_progress", "files_touched": []},
    }
    index._index_path.write_text(json.dumps(entries))
    result = index.find_by_repo("/repo/a")
    assert result is not None
    assert result.session_key == "s2"
    assert result.task == "new task"


def test_list_recent(index):
    index.add_entry("s1", "/repo/a", "first")
    index.add_entry("s2", "/repo/b", "second")
    results = index.list_recent()
    assert len(results) >= 2
    # Verify sorted by last_updated (most recent first)
    timestamps = [r.last_updated for r in results]
    assert timestamps == sorted(timestamps, reverse=True)


def test_list_recent_excludes_old(index):
    index._index_path.write_text(json.dumps({
        "old1": {
            "session_key": "old1",
            "repo": "/old",
            "task": "old task",
            "started": "2020-01-01T00:00:00Z",
            "last_updated": "2020-01-01T00:00:00Z",
            "status": "completed",
            "files_touched": [],
        }
    }))
    assert index.list_recent(days=14) == []


def test_status_global_flag(monkeypatch):
    from kadmon.memory import central_index
    from kadmon.cli import main

    fake = [
        IndexEntry(
            session_key="abc",
            repo="/foo",
            task="fix",
            started="2026-05-12T10:00:00Z",
            last_updated="2026-05-12T11:00:00Z",
            status="completed",
        )
    ]
    monkeypatch.setattr(
        central_index.CentralIndex, "list_recent", lambda self, days=14: fake
    )
    runner = CliRunner()
    result = runner.invoke(main, ["status", "--global"])
    assert "fix" in result.output
    assert "/foo" in result.output
