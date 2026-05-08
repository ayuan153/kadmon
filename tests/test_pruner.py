"""Tests for kadmon.agent.pruner.Pruner."""


import pytest

from kadmon.agent.planner import Plan, PlanStep, StepStatus
from kadmon.agent.pruner import Pruner


@pytest.fixture
def pruner():
    return Pruner()


# --- prune_for_handoff ---


def test_prune_for_handoff_with_mixed_steps(pruner):
    plan = Plan(
        goal="test",
        steps=[
            PlanStep(id="1", description="done step", status=StepStatus.DONE),
            PlanStep(id="2", description="failed step", status=StepStatus.FAILED),
            PlanStep(id="3", description="pending step", status=StepStatus.PENDING),
        ],
    )
    result = pruner.prune_for_handoff(plan, "new task")
    assert "Completed:" in result
    assert "done step" in result
    assert "Failed approaches" in result
    assert "failed step" in result
    assert "Remaining:" in result
    assert "pending step" in result


def test_prune_for_handoff_empty_plan(pruner):
    plan = Plan(goal="test", steps=[])
    assert pruner.prune_for_handoff(plan, "new task") == ""


def test_prune_for_handoff_no_plan(pruner):
    assert pruner.prune_for_handoff(None, "new task") == ""


def test_prune_for_handoff_failed_includes_notes(pruner):
    plan = Plan(
        goal="test",
        steps=[
            PlanStep(id="1", description="bad approach", status=StepStatus.FAILED, notes="timeout error"),
        ],
    )
    result = pruner.prune_for_handoff(plan, "new task")
    assert "timeout error" in result


# --- prune_library ---


def test_prune_library_archives_different_task(pruner, tmp_path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    current = tasks_dir / "current.md"
    current.write_text("# Task A\nDoing task A stuff")

    pruner.prune_library(tmp_path, "Task B")

    assert current.read_text() == ""
    archived = list((tasks_dir / "completed").iterdir())
    assert len(archived) == 1
    assert "Task A" in archived[0].read_text()


def test_prune_library_keeps_matching_task(pruner, tmp_path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    current = tasks_dir / "current.md"
    current.write_text("# Task A\nDoing task A stuff")

    pruner.prune_library(tmp_path, "Task A")

    assert current.read_text() == "# Task A\nDoing task A stuff"
    assert not (tasks_dir / "completed").exists()


def test_prune_library_empty_file(pruner, tmp_path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    current = tasks_dir / "current.md"
    current.write_text("")

    pruner.prune_library(tmp_path, "Task B")

    assert not (tasks_dir / "completed").exists()


# --- summarize_completed_work ---


def test_summarize_completed_work_single(pruner):
    plan = Plan(
        goal="test",
        steps=[PlanStep(id="1", description="wrote the tests", status=StepStatus.DONE)],
    )
    result = pruner.summarize_completed_work(plan)
    assert "wrote the tests" in result


def test_summarize_completed_work_multiple(pruner):
    plan = Plan(
        goal="test",
        steps=[
            PlanStep(id="1", description="step one", status=StepStatus.DONE),
            PlanStep(id="2", description="step two", status=StepStatus.DONE),
            PlanStep(id="3", description="step three", status=StepStatus.DONE),
        ],
    )
    result = pruner.summarize_completed_work(plan)
    assert "3" in result
    assert "step one" in result
    assert "step two" in result
    assert "step three" in result


def test_summarize_completed_work_none(pruner):
    plan = Plan(goal="test", steps=[PlanStep(id="1", description="x", status=StepStatus.PENDING)])
    assert pruner.summarize_completed_work(plan) == "No steps completed."
