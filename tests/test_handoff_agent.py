"""Tests for HandoffAgent and HandoffManager."""

from kadmon.agent.handoff import HandoffManager, HandoffTrigger
from kadmon.agent.planner import Plan, PlanStep, StepStatus
from kadmon.memory.agents.handoff_agent import HandoffAgent
from kadmon.providers.base import LLMResponse, TokenUsage


class MockProvider:
    def __init__(self, response: str):
        self._response = response
        self.called = False

    def complete(self, messages, tools=None, system=""):
        self.called = True
        return LLMResponse(content=self._response, usage=TokenUsage(input_tokens=10, output_tokens=10))


def test_handoff_agent_synthesize():
    provider = MockProvider("# Handoff\n\nDo the thing.")
    agent = HandoffAgent(provider)
    result = agent.synthesize("Fix bug", ["step1"], ["step2"], [])
    assert result == "# Handoff\n\nDo the thing."


def test_handoff_agent_format_input():
    provider = MockProvider("")
    agent = HandoffAgent(provider)
    result = agent._format_input(
        "Deploy service",
        ["wrote tests"],
        ["deploy to prod"],
        [{"event": "tool_executed", "data": {"tool": "shell", "success": True}}],
    )
    assert "Deploy service" in result
    assert "wrote tests" in result
    assert "deploy to prod" in result
    assert "shell" in result


def test_handoff_agent_truncates_events():
    provider = MockProvider("")
    agent = HandoffAgent(provider)
    events = [{"event": "tool_executed", "data": {"tool": f"tool_{i}", "success": True}} for i in range(30)]
    result = agent._format_input("goal", [], [], events)
    # Only last 20 events should appear
    assert "tool_10" in result
    assert "tool_29" in result
    assert "tool_9" not in result


def test_craft_handoff_uses_agent(tmp_path):
    provider = MockProvider("# Task: Fix auth\n\n## What's Next\n- Fix token refresh")
    mgr = HandoffManager(str(tmp_path), provider=provider)
    plan = Plan(goal="Fix auth", steps=[PlanStep(id="1", description="Fix refresh", status=StepStatus.PENDING)])
    trigger = HandoffTrigger(reason="token_budget", details="80%")
    result = mgr._craft_handoff(plan, trigger)
    assert provider.called
    assert "Fix auth" in result
    assert "What's Next" in result


def test_craft_handoff_fallback_no_provider(tmp_path):
    mgr = HandoffManager(str(tmp_path))
    plan = Plan(goal="Fix auth", steps=[PlanStep(id="1", description="Fix refresh", status=StepStatus.DONE)])
    trigger = HandoffTrigger(reason="token_budget", details="80%")
    result = mgr._craft_handoff(plan, trigger)
    assert "Fix auth" in result
    assert "Fix refresh" in result


def test_resume_prompt_no_blob():
    mgr = HandoffManager("/tmp/fake")
    cold_start = "This is cold start content that should NOT appear"
    handoff_doc = "# Handoff doc content"
    result = mgr._build_resume_prompt(cold_start, handoff_doc)
    assert cold_start not in result
    assert "# Handoff doc content" in result


def test_resume_prompt_contains_instructions():
    mgr = HandoffManager("/tmp/fake")
    result = mgr._build_resume_prompt("", "# Task brief")
    assert "library_read" in result
    assert "verify" in result
