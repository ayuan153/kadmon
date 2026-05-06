from kadmon.agent.planner import Plan, PlanStep, StepStatus
from kadmon.tools.base import Tool, ToolResult


class PlanTool(Tool):
    name = "plan"
    description = (
        "Manage the task plan. Actions: "
        "create (make a new plan), view (show current plan), "
        "update (mark step done/failed/skipped), "
        "add (add a new step after an existing one)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "view", "update", "add"],
                "description": "The action to perform",
            },
            "goal": {
                "type": "string",
                "description": "Goal for the plan (required for create)",
            },
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of step descriptions (required for create)",
            },
            "step_id": {
                "type": "string",
                "description": "Step ID to update or add after",
            },
            "status": {
                "type": "string",
                "enum": ["done", "failed", "skipped"],
                "description": "New status for the step (for update action)",
            },
            "notes": {
                "type": "string",
                "description": "Notes about the step",
            },
            "description": {
                "type": "string",
                "description": "Description for a new step (for add action)",
            },
        },
        "required": ["action"],
    }

    def __init__(self):
        self._plan: Plan | None = None

    @property
    def plan(self) -> Plan | None:
        return self._plan

    def execute(self, action: str, **kwargs) -> ToolResult:
        if action == "create":
            return self._create(kwargs.get("goal", ""), kwargs.get("steps", []))
        elif action == "view":
            return self._view()
        elif action == "update":
            return self._update(
                kwargs.get("step_id", ""), kwargs.get("status", ""), kwargs.get("notes", "")
            )
        elif action == "add":
            return self._add(
                kwargs.get("step_id", ""), kwargs.get("description", ""), kwargs.get("notes", "")
            )
        return ToolResult(output=f"Unknown action: {action}", error=True)

    def _create(self, goal: str, steps: list[str]) -> ToolResult:
        if not goal or not steps:
            return ToolResult(output="Error: goal and steps are required for create", error=True)
        plan_steps = [PlanStep(id=str(i + 1), description=desc) for i, desc in enumerate(steps)]
        self._plan = Plan(goal=goal, steps=plan_steps)
        return ToolResult(
            output=f"Plan created with {len(steps)} steps.\n\n{self._plan.to_prompt()}"
        )

    def _view(self) -> ToolResult:
        if not self._plan:
            return ToolResult(output="No plan exists. Use action=create to make one.")
        return ToolResult(output=self._plan.to_prompt())

    def _update(self, step_id: str, status: str, notes: str) -> ToolResult:
        if not self._plan:
            return ToolResult(output="No plan exists.", error=True)
        if not step_id or not status:
            return ToolResult(output="Error: step_id and status required for update", error=True)
        status_map = {
            "done": StepStatus.DONE,
            "failed": StepStatus.FAILED,
            "skipped": StepStatus.SKIPPED,
        }
        s = status_map.get(status)
        if not s:
            return ToolResult(
                output=f"Invalid status: {status}. Use done/failed/skipped.", error=True
            )
        if s == StepStatus.DONE:
            self._plan.mark_done(step_id, notes)
        elif s == StepStatus.FAILED:
            self._plan.mark_failed(step_id, notes)
        else:
            step = self._plan._get(step_id)
            if step:
                step.status = StepStatus.SKIPPED
        return ToolResult(output=f"Step {step_id} marked as {status}.\n\n{self._plan.to_prompt()}")

    def _add(self, after_id: str, description: str, notes: str) -> ToolResult:
        if not self._plan:
            return ToolResult(output="No plan exists.", error=True)
        if not description:
            return ToolResult(output="Error: description required for add", error=True)
        new_id = str(len(self._plan.steps) + 1)
        new_step = PlanStep(id=new_id, description=description, notes=notes)
        if after_id:
            self._plan.add_step_after(after_id, new_step)
        else:
            self._plan.steps.append(new_step)
        return ToolResult(output=f"Step {new_id} added.\n\n{self._plan.to_prompt()}")
