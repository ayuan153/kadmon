from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class ToolResult:
    output: str
    error: bool = False


class Tool(ABC):
    name: str
    description: str
    parameters: dict  # JSON Schema

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult: ...

    def definition(self) -> dict:
        return {'name': self.name, 'description': self.description, 'input_schema': self.parameters}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def definitions(self) -> list[dict]:
        return [t.definition() for t in self._tools.values()]

    def execute(self, name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(output=f'Unknown tool: {name}', error=True)
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(output=f'Tool error: {e}', error=True)
