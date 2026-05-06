from kadmon.providers.base import LLMProvider, Message
from kadmon.tools.base import ToolRegistry
from kadmon.agent.context import ContextManager
from kadmon.agent.prompts import SYSTEM_PROMPT
from kadmon.agent.recovery import LoopDetector


class AgentLoop:
    def __init__(self, provider: LLMProvider, tools: ToolRegistry, max_iterations: int = 50):
        self.provider = provider
        self.tools = tools
        self.max_iterations = max_iterations
        self.context = ContextManager()
        self.loop_detector = LoopDetector()

    def run(self, task: str) -> str:
        """Run the agent loop. Returns the final patch or empty string."""
        self.context.add(Message(role='user', content=task))

        for _ in range(self.max_iterations):
            response = self.provider.complete(
                messages=self.context.to_messages(),
                tools=self.tools.definitions(),
                system=SYSTEM_PROMPT,
            )

            if not response.tool_calls:
                self.context.add(Message(role='assistant', content=response.content))
                continue

            # Build assistant content blocks (text + tool_use)
            assistant_content: list[dict] = []
            if response.content:
                assistant_content.append({'type': 'text', 'text': response.content})
            for tc in response.tool_calls:
                assistant_content.append({
                    'type': 'tool_use', 'id': tc.id, 'name': tc.name, 'input': tc.arguments,
                })
            self.context.add(Message(role='assistant', content=assistant_content))

            # Execute tools and build result blocks
            tool_results: list[dict] = []
            loop_detected = False
            for tc in response.tool_calls:
                result = self.tools.execute(tc.name, **tc.arguments)

                if tc.name == 'submit' and not result.error:
                    return result.output

                if self.loop_detector.record_action(tc.name, tc.arguments):
                    loop_detected = True
                if result.error and self.loop_detector.record_error(result.output):
                    loop_detected = True

                tool_results.append({
                    'type': 'tool_result',
                    'tool_use_id': tc.id,
                    'content': result.output,
                    **(({'is_error': True}) if result.error else {}),
                })

            self.context.add(Message(role='user', content=tool_results))

            if loop_detected:
                self.context.add(Message(role='user', content=self.loop_detector.get_recovery_message()))
                self.loop_detector.reset()

        return ''
