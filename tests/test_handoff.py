"""Tests for kadmon Phase 4c: autonomous handoff system."""

from unittest.mock import MagicMock


from kadmon.agent.context import ContextManager
from kadmon.agent.handoff import HandoffManager, HandoffMonitor, HandoffTrigger
from kadmon.agent.planner import Plan, PlanStep, StepStatus


# --- HandoffMonitor ---


def test_monitor_no_trigger():
    ctx = ContextManager(max_tokens=1000)
    ctx._token_estimate = 100  # 10% utilization
    plan = Plan(goal="test", steps=[PlanStep(id="1", description="step1")])
    monitor = HandoffMonitor()
    assert monitor.check(ctx, plan) is None


def test_monitor_token_budget():
    ctx = ContextManager(max_tokens=1000)
    ctx._token_estimate = 900  # 90% > 80% threshold
    monitor = HandoffMonitor()
    trigger = monitor.check(ctx)
    assert trigger is not None
    assert trigger.reason == "token_budget"


def test_monitor_task_boundary():
    plan = Plan(goal="test", steps=[
        PlanStep(id="1", description="s1", status=StepStatus.DONE),
        PlanStep(id="2", description="s2", status=StepStatus.DONE),
    ])
    ctx = ContextManager(max_tokens=1000)
    # Clean break requires substantial context (>40% utilization)
    ctx._token_estimate = 450  # 45% utilization
    monitor = HandoffMonitor()
    trigger = monitor.check(ctx, plan)
    assert trigger is not None
    assert trigger.reason == "clean_break"


def test_monitor_quality_degradation():
    ctx = ContextManager(max_tokens=1000)
    monitor = HandoffMonitor()
    for _ in range(5):
        monitor.record_loop_recovery()
    trigger = monitor.check(ctx)
    assert trigger is not None
    assert trigger.reason == "quality_degradation"


def test_monitor_reset():
    ctx = ContextManager(max_tokens=1000)
    monitor = HandoffMonitor()
    for _ in range(5):
        monitor.record_loop_recovery()
    assert monitor.check(ctx) is not None
    monitor.reset()
    assert monitor.check(ctx) is None


# --- HandoffManager ---


def test_craft_handoff_with_plan(tmp_path):
    mgr = HandoffManager(repo_root=str(tmp_path))
    plan = Plan(goal="Build feature X", steps=[
        PlanStep(id="1", description="Design", status=StepStatus.DONE, notes="Done well"),
        PlanStep(id="2", description="Implement", status=StepStatus.ACTIVE),
        PlanStep(id="3", description="Test", status=StepStatus.PENDING),
    ])
    trigger = HandoffTrigger(reason="token_budget", details="Context at 85%")
    doc = mgr._craft_handoff(plan, trigger)
    assert "## Accomplished" in doc
    assert "Design" in doc
    assert "## In Progress" in doc
    assert "Implement" in doc
    assert "## Remaining Plan" in doc
    assert "Test" in doc
    assert "## Goal" in doc
    assert "Build feature X" in doc


def test_craft_handoff_no_plan(tmp_path):
    mgr = HandoffManager(repo_root=str(tmp_path))
    trigger = HandoffTrigger(reason="token_budget", details="Context at 85%")
    doc = mgr._craft_handoff(None, trigger)
    assert "No structured plan was active at handoff time" in doc


def test_execute_resets_context(tmp_path):
    ctx = ContextManager(max_tokens=1000)
    ctx._token_estimate = 500
    ctx.messages.append(MagicMock())  # simulate existing message
    mgr = HandoffManager(repo_root=str(tmp_path))
    trigger = HandoffTrigger(reason="token_budget", details="test")
    resume = mgr.execute(ctx, None, trigger)
    assert ctx.messages == []
    assert "resuming work after a context handoff" in resume


def test_execute_saves_files(tmp_path):
    ctx = ContextManager(max_tokens=1000)
    mgr = HandoffManager(repo_root=str(tmp_path))
    trigger = HandoffTrigger(reason="clean_break", details="done")
    mgr.execute(ctx, None, trigger)
    assert (tmp_path / "docs" / "handoffs" / "latest.md").exists()


def test_execute_marks_session_handed_off(tmp_path):
    ctx = ContextManager(max_tokens=1000)
    tracker = MagicMock()
    mgr = HandoffManager(repo_root=str(tmp_path), session_tracker=tracker)
    trigger = HandoffTrigger(reason="token_budget", details="test")
    mgr.execute(ctx, None, trigger)
    tracker.mark_handed_off.assert_called_once()
