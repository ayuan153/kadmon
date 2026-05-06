from unittest.mock import MagicMock

from kadmon.agent.context import ContextManager
from kadmon.agent.loop import AgentLoop
from kadmon.providers.base import LLMResponse, Message, ToolCall
from kadmon.tools.base import Tool, ToolRegistry, ToolResult


class DummyTool(Tool):
    name = 'dummy'
    description = 'A dummy tool'
    parameters = {'type': 'object', 'properties': {}, 'required': []}

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(output='dummy result')


def test_context_manager_add():
    cm = ContextManager(max_tokens=100000)
    cm.add(Message(role='user', content='hello'))
    cm.add(Message(role='assistant', content='hi'))
    msgs = cm.to_messages()
    assert len(msgs) == 2
    assert msgs[0].role == 'user'
    assert msgs[1].content == 'hi'


def test_context_manager_compaction():
    cm = ContextManager(max_tokens=100)  # Very small budget
    for i in range(20):
        cm.add(Message(role='user', content='x' * 100))
    # Should have compacted - fewer than 20 messages
    assert len(cm.to_messages()) < 20
    assert len(cm.to_messages()) >= 4  # Keeps at least 4


def test_agent_loop_no_tools():
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(content='done', tool_calls=[], stop_reason='end_turn')
    registry = ToolRegistry()
    agent = AgentLoop(provider=provider, tools=registry, max_iterations=3)
    result = agent.run('do something')
    # No submit called, loop exhausts iterations returning text only
    assert result == ''


def test_agent_loop_with_submit():
    provider = MagicMock()
    # Provider returns a submit tool call
    provider.complete.return_value = LLMResponse(
        content='',
        tool_calls=[ToolCall(id='tc1', name='submit', arguments={})],
    )

    class FakeSubmit(Tool):
        name = 'submit'
        description = 'submit'
        parameters = {'type': 'object', 'properties': {}, 'required': []}

        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(output='diff --git a/f.txt')

    registry = ToolRegistry()
    registry.register(FakeSubmit())
    agent = AgentLoop(provider=provider, tools=registry, max_iterations=5)
    result = agent.run('fix bug')
    assert 'diff --git' in result


def test_agent_loop_max_iterations():
    provider = MagicMock()
    # Always returns a non-submit tool call
    provider.complete.return_value = LLMResponse(
        content='',
        tool_calls=[ToolCall(id='tc1', name='dummy', arguments={})],
    )
    registry = ToolRegistry()
    registry.register(DummyTool())
    agent = AgentLoop(provider=provider, tools=registry, max_iterations=3)
    result = agent.run('loop forever')
    assert result == ''
    assert provider.complete.call_count == 3
