from __future__ import annotations

from typing import TYPE_CHECKING

from kadmon.providers.base import LLMProvider, Message
from kadmon.tools.base import ToolRegistry
from kadmon.agent.context import ContextManager
from kadmon.agent.prompts import SYSTEM_PROMPT, ARCHITECT_PROMPT, EDITOR_PROMPT
from kadmon.agent.recovery import LoopDetector
from kadmon.tools.plan import PlanTool

if TYPE_CHECKING:
    from kadmon.human.channel import HumanChannel
    from kadmon.memory.librarian import Librarian
    from kadmon.memory.session_tracker import SessionTracker


# Tools available in each mode
ARCHITECT_TOOLS = {
    "read_file",
    "list_dir",
    "grep_search",
    "file_skeleton",
    "find_references",
    "find_definition",
    "plan",
    "shell",
    "ask_human",
    "library_read",
    "library_status",
}
EDITOR_TOOLS = {"read_file", "edit_file", "write_file", "shell", "submit", "plan", "ask_human", "library_write"}


class AgentLoop:
    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        max_iterations: int = 50,
        use_planning: bool = True,
        librarian: Librarian | None = None,
        session_tracker: SessionTracker | None = None,
        mode: str = "cautious",
        channel: HumanChannel | None = None,
        repo_root: str = ".",
        display=None,
    ):
        self.provider = provider
        self.tools = tools
        self.max_iterations = max_iterations
        self.use_planning = use_planning
        self.librarian = librarian
        self.session_tracker = session_tracker
        self.mode = mode
        self.display = display
        self.context = ContextManager()
        self.loop_detector = LoopDetector()
        # Handoff system (autonomous context management)
        self._handoff_monitor = None
        self._handoff_manager = None
        if librarian or session_tracker:
            from kadmon.agent.handoff import HandoffManager, HandoffMonitor

            self._handoff_monitor = HandoffMonitor()
            self._handoff_manager = HandoffManager(
                repo_root=repo_root, librarian=librarian, session_tracker=session_tracker
            )
        # Register plan tool
        self._plan_tool = PlanTool()
        self.tools.register(self._plan_tool)
        # Register ask_human tool when channel provided (ambiguity resolution, not permission)
        if channel:
            from kadmon.tools.ask_human import AskHumanTool

            self.tools.register(AskHumanTool(channel))

    def run(self, task: str) -> str:
        """Run the agent loop. Returns the final patch or empty string."""
        # Start session tracking
        if self.session_tracker:
            self.session_tracker.start(task)

        if self.use_planning:
            return self._run_with_planning(task)
        return self._run_simple(task)

    def _run_with_planning(self, task: str) -> str:
        """Two-phase: architect explores and plans, editor executes."""
        # Phase 1: Architect
        self.context.add(Message(role="user", content=task))
        architect_budget = self.max_iterations // 3  # ~1/3 budget for planning

        for _ in range(architect_budget):
            response = self._call_llm(
                tools=self._filtered_tools(ARCHITECT_TOOLS),
                system=ARCHITECT_PROMPT,
            )
            done = self._process_response(response)
            if done:
                return done
            # If plan was created, switch to editor phase
            if self._plan_tool.plan and self._plan_tool.plan.steps:
                break

        # Phase 2: Editor (uses remaining budget)
        editor_budget = self.max_iterations - architect_budget
        # Inject plan context
        if self._plan_tool.plan:
            plan_msg = (
                f"Plan created. Now execute it step by step:\n\n{self._plan_tool.plan.to_prompt()}"
            )
            self.context.add(Message(role="user", content=plan_msg))

        for _ in range(editor_budget):
            response = self._call_llm(
                tools=self._filtered_tools(EDITOR_TOOLS),
                system=EDITOR_PROMPT,
            )
            done = self._process_response(response)
            if done:
                return done
            # Check if handoff should trigger
            if self._check_handoff():
                continue  # Context was reset, loop continues with fresh state

        return ""

    def _run_simple(self, task: str) -> str:
        """Simple ReAct loop without planning (for benchmarks or simple tasks)."""
        self.context.add(Message(role="user", content=task))

        for _ in range(self.max_iterations):
            response = self._call_llm(
                tools=self.tools.definitions(),
                system=SYSTEM_PROMPT,
            )
            done = self._process_response(response)
            if done:
                return done

        return ""

    def _process_response(self, response) -> str | None:
        """Process an LLM response. Returns patch string if submit called, else None."""
        if not response.tool_calls:
            self.context.add(Message(role="assistant", content=response.content))
            # Must end with user message for next API call
            self.context.add(
                Message(role="user", content="[System: if you have completed your response, call submit. If you need to do more work, use tools. If you are waiting for user input, call ask_human.]")
            )
            return None

        # Build assistant content blocks
        assistant_content: list[dict] = []
        if response.content:
            assistant_content.append({"type": "text", "text": response.content})
        for tc in response.tool_calls:
            assistant_content.append(
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                }
            )
        self.context.add(Message(role="assistant", content=assistant_content))

        # Execute tools
        tool_results: list[dict] = []
        loop_detected = False
        for tc in response.tool_calls:
            result = self.tools.execute(tc.name, **tc.arguments)

            if tc.name == "submit" and not result.error:
                if self.display:
                    self.display.show_submit(result.output)
                if self.session_tracker:
                    self.session_tracker.complete_session()
                if self.librarian:
                    self.librarian.save_task_context(
                        self._plan_tool.plan.goal if self._plan_tool.plan else "task",
                        "Task completed. Patch submitted.",
                    )
                return result.output

            if self.loop_detector.record_action(tc.name, tc.arguments):
                loop_detected = True
            if result.error and self.loop_detector.record_error(result.output):
                loop_detected = True

            if self.display and tc.name != "submit":
                self.display.show_tool_result(tc.name, result.output, result.error)

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result.output,
                    **(({"is_error": True}) if result.error else {}),
                }
            )

        self.context.add(Message(role="user", content=tool_results))

        # Auto-save on plan step completion
        if self.librarian and self._plan_tool.plan:
            plan = self._plan_tool.plan
            for tc in response.tool_calls:
                if (
                    tc.name == "plan"
                    and tc.arguments.get("action") == "update"
                    and tc.arguments.get("status") == "done"
                ):
                    step_id = tc.arguments.get("step_id", "")
                    step = plan._get(step_id)
                    if step:
                        self.librarian.save_task_context(
                            plan.goal,
                            f"Completed step {step_id}: {step.description}\n\nPlan progress:\n{plan.to_prompt()}",
                        )

        if loop_detected:
            self.context.add(
                Message(role="user", content=self.loop_detector.get_recovery_message())
            )
            self.loop_detector.reset()
            if self._handoff_monitor:
                self._handoff_monitor.record_loop_recovery()

        return None

    def _check_handoff(self) -> bool:
        """Check if handoff should trigger. If so, execute it and return True."""
        if not self._handoff_monitor or not self._handoff_manager:
            return False
        plan = self._plan_tool.plan
        trigger = self._handoff_monitor.check(self.context, plan)
        if not trigger:
            return False
        # Execute handoff
        resume_prompt = self._handoff_manager.execute(self.context, plan, trigger)
        self.context.add(Message(role="user", content=resume_prompt))
        self._handoff_monitor.reset()
        return True

    def _call_llm(self, tools: list[dict], system: str):
        """Call LLM with streaming if display is set, otherwise use complete()."""
        if self.display and hasattr(self.provider, "stream"):
            from kadmon.providers.base import StreamEvent

            response = None
            for chunk in self.provider.stream(
                messages=self.context.to_messages(), tools=tools, system=system
            ):
                self.display.handle(chunk)
                if chunk.event == StreamEvent.DONE:
                    response = chunk.response
            return response
        return self.provider.complete(
            messages=self.context.to_messages(), tools=tools, system=system
        )

    def _filtered_tools(self, allowed: set[str]) -> list[dict]:
        """Return tool definitions filtered to the allowed set."""
        return [t for t in self.tools.definitions() if t["name"] in allowed]
