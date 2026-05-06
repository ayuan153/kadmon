from kadmon.tools.base import Tool as Tool, ToolResult as ToolResult, ToolRegistry as ToolRegistry
from kadmon.tools.file_io import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from kadmon.tools.search import GrepSearchTool
from kadmon.tools.shell import ShellTool
from kadmon.tools.submit import SubmitTool


def create_default_registry(repo_root: str) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ReadFileTool(repo_root))
    registry.register(WriteFileTool(repo_root))
    registry.register(EditFileTool(repo_root))
    registry.register(ListDirTool(repo_root))
    registry.register(GrepSearchTool(repo_root))
    registry.register(ShellTool(repo_root))
    registry.register(SubmitTool(repo_root))
    return registry
