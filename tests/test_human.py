"""Tests for Phase 4b: human-in-the-loop system."""
import json
from unittest.mock import MagicMock

from kadmon.human.channel import Answer, CLIChannel, Question, QuestionBatcher, WebhookChannel
from kadmon.tools.ask_human import AskHumanTool
from kadmon.tools.base import ToolRegistry


# --- QuestionBatcher tests ---


def test_batcher_add():
    batcher = QuestionBatcher()
    q = Question(text="What color?")
    qid = batcher.add(q)
    assert qid == "q1"
    assert q.id == "q1"
    assert batcher.pending_count == 1


def test_batcher_flush():
    batcher = QuestionBatcher()
    for i in range(3):
        batcher.add(Question(text=f"Q{i}"))
    batch = batcher.flush()
    assert len(batch) == 3
    assert batcher.pending_count == 0


def test_batcher_is_full():
    batcher = QuestionBatcher(max_batch_size=3)
    for i in range(3):
        batcher.add(Question(text=f"Q{i}"))
    assert batcher.is_full()


def test_batcher_is_ready():
    batcher = QuestionBatcher()
    assert not batcher.is_ready()
    batcher.add(Question(text="hi"))
    assert batcher.is_ready()


# --- CLIChannel tests ---


def test_cli_channel_ask(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "my answer")
    channel = CLIChannel()
    questions = [Question(text="What?", id="q1"), Question(text="Why?", id="q2")]
    answers = channel.ask(questions)
    assert len(answers) == 2
    assert all(isinstance(a, Answer) for a in answers)
    assert answers[0].question_id == "q1"
    assert answers[0].text == "my answer"


def test_cli_channel_options(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "2")
    channel = CLIChannel()
    questions = [Question(text="Pick one", id="q1", options=["alpha", "beta", "gamma"])]
    answers = channel.ask(questions)
    assert answers[0].text == "beta"


# --- AskHumanTool tests ---


def test_ask_human_tool():
    mock_channel = MagicMock()
    mock_channel.ask.return_value = [Answer(question_id="q1", text="yes")]
    tool = AskHumanTool(mock_channel)
    result = tool.execute(questions=[{"text": "Continue?"}])
    assert not result.error
    assert "yes" in result.output
    mock_channel.ask.assert_called_once()


def test_ask_human_tool_no_questions():
    mock_channel = MagicMock()
    tool = AskHumanTool(mock_channel)
    result = tool.execute(questions=[])
    assert result.error
    assert "Error" in result.output


def test_ask_human_not_registered_in_yolo():
    from kadmon.agent.loop import AgentLoop

    provider = MagicMock()
    registry = ToolRegistry()
    channel = MagicMock()
    agent = AgentLoop(
        provider=provider, tools=registry, mode="yolo", channel=channel, use_planning=False
    )
    tool_names = [t["name"] for t in agent.tools.definitions()]
    assert "ask_human" not in tool_names


def test_ask_human_registered_in_cautious():
    from kadmon.agent.loop import AgentLoop

    provider = MagicMock()
    registry = ToolRegistry()
    channel = MagicMock()
    agent = AgentLoop(
        provider=provider, tools=registry, mode="cautious", channel=channel, use_planning=False
    )
    tool_names = [t["name"] for t in agent.tools.definitions()]
    assert "ask_human" in tool_names


# --- WebhookChannel tests ---


def test_webhook_notify(monkeypatch):
    captured = {}

    def mock_urlopen(req, **kwargs):
        captured["url"] = req.full_url
        captured["data"] = json.loads(req.data)
        captured["method"] = req.method

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    channel = WebhookChannel(push_url="http://example.com/hook")
    channel.notify("build done")
    assert captured["url"] == "http://example.com/hook"
    assert captured["method"] == "POST"
    assert captured["data"]["type"] == "notification"
    assert captured["data"]["message"] == "build done"
