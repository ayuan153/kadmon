from kadmon.checkpoints import CheckpointManager
from kadmon.index.db import SymbolDB
from kadmon.index.parser import SymbolParser
from kadmon.index.updater import IndexUpdater
from kadmon.memory.read_cache import ReadCache
from kadmon.tools.base import Tool as Tool, ToolResult as ToolResult, ToolRegistry as ToolRegistry
from kadmon.tools.checkpoint import CheckpointRollbackTool
from kadmon.tools.file_io import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from kadmon.tools.library import LibraryReadTool, LibraryWriteTool, LibraryStatusTool
from kadmon.tools.references import FindReferencesTool, FindDefinitionTool
from kadmon.tools.search import GrepSearchTool
from kadmon.tools.shell import ShellTool
from kadmon.tools.skeleton import FileSkeletonTool
from kadmon.tools.submit import SubmitTool

from kadmon.providers.base import LLMProvider


def create_default_registry(repo_root: str, db: SymbolDB | None = None, provider: LLMProvider | None = None) -> ToolRegistry:
    registry = ToolRegistry()
    cache = ReadCache()
    checkpoint_mgr = CheckpointManager(repo_root)
    registry.register(ReadFileTool(repo_root, read_cache=cache))
    registry.register(WriteFileTool(repo_root, read_cache=cache, checkpoint_manager=checkpoint_mgr))
    registry.register(EditFileTool(repo_root, read_cache=cache, checkpoint_manager=checkpoint_mgr))
    registry.register(ListDirTool(repo_root))
    registry.register(GrepSearchTool(repo_root))
    registry.register(ShellTool(repo_root))
    registry.register(SubmitTool(repo_root))
    registry.register(FileSkeletonTool(repo_root))
    registry.register(CheckpointRollbackTool(checkpoint_mgr))
    if db:
        registry.register(FindReferencesTool(db))
        registry.register(FindDefinitionTool(db))
    if provider:
        read_tool = LibraryReadTool(provider, repo_root)
        write_tool = LibraryWriteTool(provider, repo_root)
        registry.register(read_tool)
        registry.register(write_tool)
        registry.register(LibraryStatusTool(repo_root, read_tracker=read_tool.tracker, write_tracker=write_tool.tracker))
    else:
        registry.register(LibraryStatusTool(repo_root))
    return registry


def build_index(repo_root: str) -> SymbolDB:
    """Build or update the symbol index for a repo. Returns the SymbolDB instance."""
    from pathlib import Path

    db_path = str(Path(repo_root) / ".kadmon" / "symbols.db")
    db = SymbolDB(db_path)
    parser = SymbolParser()
    updater = IndexUpdater(db=db, repo_root=repo_root)
    updater.update(parser.parse_file)
    return db
