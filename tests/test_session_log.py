import json

from kadmon.memory.session_log import EventType, SessionLogger


def test_session_start_creates_log(tmp_path):
    logger = SessionLogger(str(tmp_path))
    logger.session_start("do stuff")
    log_file = tmp_path / ".kadmon" / "sessions" / "log.jsonl"
    line = json.loads(log_file.read_text().strip())
    assert line["event"] == "session_start"
    assert line["data"]["task"] == "do stuff"
    assert "timestamp" in line


def test_append_multiple_events(tmp_path):
    logger = SessionLogger(str(tmp_path))
    logger.append(EventType.SESSION_START, task="a")
    logger.append(EventType.SESSION_END, status="done")
    log_file = tmp_path / ".kadmon" / "sessions" / "log.jsonl"
    lines = [line for line in log_file.read_text().strip().split("\n") if line]
    assert len(lines) == 2


def test_read_events(tmp_path):
    logger = SessionLogger(str(tmp_path))
    logger.session_start("t1")
    logger.session_end("ok")
    events = logger.read_events()
    assert len(events) == 2
    assert events[0]["event"] == "session_start"
    assert events[1]["event"] == "session_end"


def test_read_events_empty(tmp_path):
    logger = SessionLogger(str(tmp_path))
    assert logger.read_events() == []


def test_clear_removes_log(tmp_path):
    logger = SessionLogger(str(tmp_path))
    logger.session_start("x")
    logger.clear()
    assert logger.read_events() == []
    assert not (tmp_path / ".kadmon" / "sessions" / "log.jsonl").exists()


def test_tool_executed_truncates_args(tmp_path):
    logger = SessionLogger(str(tmp_path))
    long_val = "x" * 300
    logger.tool_executed("grep", {"query": long_val}, success=True)
    events = logger.read_events()
    assert len(events) == 1
    assert len(events[0]["data"]["args"]["query"]) <= 200


def test_plan_created_event(tmp_path):
    logger = SessionLogger(str(tmp_path))
    logger.plan_created("build app", ["step1", "step2"])
    events = logger.read_events()
    assert events[0]["event"] == "plan_created"
    assert events[0]["data"]["goal"] == "build app"
    assert events[0]["data"]["steps"] == ["step1", "step2"]


def test_step_completed_event(tmp_path):
    logger = SessionLogger(str(tmp_path))
    logger.step_completed("s1", "done", notes="all good")
    events = logger.read_events()
    assert events[0]["event"] == "step_completed"
    assert events[0]["data"]["step_id"] == "s1"
    assert events[0]["data"]["status"] == "done"
    assert events[0]["data"]["notes"] == "all good"


def test_session_end_event(tmp_path):
    logger = SessionLogger(str(tmp_path))
    logger.session_end("completed")
    events = logger.read_events()
    assert events[0]["event"] == "session_end"
    assert events[0]["data"]["status"] == "completed"


def test_creates_directories(tmp_path):
    sessions_dir = tmp_path / ".kadmon" / "sessions"
    assert not sessions_dir.exists()
    SessionLogger(str(tmp_path))
    assert sessions_dir.exists()
