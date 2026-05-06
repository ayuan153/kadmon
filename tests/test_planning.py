"""Tests for Phase 3: planning system, backtracking, and architect/editor loop."""
from unittest.mock import MagicMock


from kadmon.agent.backtrack import BacktrackManager
from kadmon.agent.loop import AgentLoop
from kadmon.agent.planner import Plan, PlanStep, StepStatus
from kadmon.providers.base import LLMResponse, ToolCall
from kadmon.tools.base import Tool, ToolRegistry, ToolResult
from kadmon.tools.plan import PlanTool


# --- Plan dataclass tests ---


def test_plan_create():
    steps = [PlanStep(id="1", description="first"), PlanStep(id="2", description="second")]
    plan = Plan(goal="test goal", steps=steps)
    assert plan.current_step() == steps[0]
    assert plan.current_step().status == StepStatus.PENDING


def test_plan_mark_done():
    steps = [PlanStep(id="1", description="first"), PlanStep(id="2", description="second")]
    plan = Plan(goal="g", steps=steps)
    plan.mark_done("1")
    assert steps[0].status == StepStatus.DONE
    assert plan.current_step() == steps[1]


def test_plan_mark_failed():
    steps = [PlanStep(id="1", description="first")]
    plan = Plan(goal="g", steps=steps)
    plan.mark_failed("1", notes="broken")
    assert steps[0].status == StepStatus.FAILED
    assert steps[0].attempts == 1
    assert steps[0].notes == "broken"


def test_plan_is_complete():
    steps = [
        PlanStep(id="1", description="a", status=StepStatus.DONE),
        PlanStep(id="2", description="b", status=StepStatus.SKIPPED),
        PlanStep(id="3", description="c", status=StepStatus.FAILED),
    ]
    plan = Plan(goal="g", steps=steps)
    assert plan.is_complete()


def test_plan_add_step_after():
    steps = [PlanStep(id="1", description="first"), PlanStep(id="2", description="second")]
    plan = Plan(goal="g", steps=steps)
    new_step = PlanStep(id="1.5", description="inserted")
    plan.add_step_after("1", new_step)
    assert plan.steps[1] == new_step
    assert len(plan.steps) == 3


def test_plan_to_prompt():
    steps = [
        PlanStep(id="1", description="do thing", status=StepStatus.DONE),
        PlanStep(id="2", description="next thing", status=StepStatus.ACTIVE),
        PlanStep(id="3", description="last thing", status=StepStatus.PENDING),
    ]
    plan = Plan(goal="my goal", steps=steps)
    output = plan.to_prompt()
    assert "Plan: my goal" in output
    assert "[x]" in output
    assert "[>]" in output
    assert "[ ]" in output


# --- PlanTool tests ---


def test_plan_tool_create():
    tool = PlanTool()
    result = tool.execute(action="create", goal="build feature", steps=["step a", "step b"])
    assert not result.error
    assert tool.plan is not None
    assert len(tool.plan.steps) == 2
    assert tool.plan.goal == "build feature"


def test_plan_tool_view_empty():
    tool = PlanTool()
    result = tool.execute(action="view")
    assert "No plan exists" in result.output


def test_plan_tool_update():
    tool = PlanTool()
    tool.execute(action="create", goal="g", steps=["s1", "s2"])
    result = tool.execute(action="update", step_id="1", status="done")
    assert not result.error
    assert tool.plan.steps[0].status == StepStatus.DONE


def test_plan_tool_add():
    tool = PlanTool()
    tool.execute(action="create", goal="g", steps=["s1"])
    result = tool.execute(action="add", step_id="1", description="new step")
    assert not result.error
    assert len(tool.plan.steps) == 2
    assert tool.plan.steps[1].description == "new step"


# --- BacktrackManager tests (mock checkpoint) ---


class MockCheckpointManager:
    def __init__(self):
        self.saves = []
        self.restores = 0
        self.has_checkpoints = True

    def save(self, label: str = ""):
        self.saves.append(label)

    def restore(self, checkpoint_id: str = ""):
        self.restores += 1


def test_backtrack_on_tool_result_no_loop():
    mgr = BacktrackManager(MockCheckpointManager())
    # Varied actions should not trigger recovery
    result1 = mgr.on_tool_result("read_file", {"path": "a.py"}, error=False)
    result2 = mgr.on_tool_result("edit_file", {"path": "b.py"}, error=False)
    result3 = mgr.on_tool_result("shell", {"cmd": "test"}, error=False)
    assert result1 is None
    assert result2 is None
    assert result3 is None


def test_backtrack_on_tool_result_loop():
    mgr = BacktrackManager(MockCheckpointManager())
    # Same action repeated 3 times triggers loop detection
    same_args = {"path": "x.py"}
    mgr.on_tool_result("read_file", same_args, error=False)
    mgr.on_tool_result("read_file", same_args, error=False)
    result = mgr.on_tool_result("read_file", same_args, error=False)
    assert result is not None
    assert "STOP" in result


def test_should_backtrack():
    mgr = BacktrackManager(MockCheckpointManager())
    steps = [PlanStep(id="1", description="task", attempts=2, max_attempts=2)]
    plan = Plan(goal="g", steps=steps)
    assert mgr.should_backtrack(plan)


def test_backtrack_marks_failed():
    mock_cp = MockCheckpointManager()
    mgr = BacktrackManager(mock_cp)
    steps = [PlanStep(id="1", description="task", status=StepStatus.ACTIVE, attempts=2)]
    plan = Plan(goal="g", steps=steps)
    result = mgr.backtrack(plan)
    assert steps[0].status == StepStatus.FAILED
    assert "BACKTRACK" in result
    assert mock_cp.restores == 1


def test_backtrack_max_reached():
    mgr = BacktrackManager(MockCheckpointManager(), max_backtracks=1)
    steps = [PlanStep(id="1", description="t", status=StepStatus.ACTIVE, attempts=2)]
    plan = Plan(goal="g", steps=steps)
    mgr.backtrack(plan)  # uses the one allowed backtrack
    # Now add another active step
    plan.steps.append(PlanStep(id="2", description="t2", status=StepStatus.ACTIVE, attempts=2))
    result = mgr.backtrack(plan)
    assert "Maximum backtracks reached" in result


# --- AgentLoop architect/editor tests (mock provider) ---


class FakeSubmit(Tool):
    name = "submit"
    description = "submit"
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(output="patch-output")


def test_loop_simple_mode():
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(
        content="",
        tool_calls=[ToolCall(id="t1", name="submit", arguments={})],
    )
    registry = ToolRegistry()
    registry.register(FakeSubmit())
    agent = AgentLoop(provider=provider, tools=registry, max_iterations=5, use_planning=False)
    result = agent.run("fix it")
    assert result == "patch-output"
    # Verify system prompt used was SYSTEM_PROMPT (simple mode)
    call_kwargs = provider.complete.call_args
    from kadmon.agent.prompts import SYSTEM_PROMPT
    assert call_kwargs.kwargs["system"] == SYSTEM_PROMPT


def test_loop_planning_mode():
    provider = MagicMock()
    call_count = [0]

    def fake_complete(messages, tools=None, system=""):
        call_count[0] += 1
        if call_count[0] == 1:
            # Architect creates a plan
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="plan",
                        arguments={"action": "create", "goal": "fix bug", "steps": ["read", "edit"]},
                    )
                ],
            )
        else:
            # Editor submits
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(id="t2", name="submit", arguments={})],
            )

    provider.complete.side_effect = fake_complete
    registry = ToolRegistry()
    registry.register(FakeSubmit())
    agent = AgentLoop(provider=provider, tools=registry, max_iterations=10, use_planning=True)
    result = agent.run("fix bug")
    assert result == "patch-output"
    # Should have called complete at least twice (architect + editor)
    assert provider.complete.call_count >= 2
