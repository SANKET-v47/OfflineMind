"""Tool manager and sandboxed execution orchestrator."""

from __future__ import annotations
import logging
from typing import Dict, List, Optional, Any

from offlinemind.tools.base import Tool, ToolResult
from offlinemind.tools.calculator import CalculatorTool
from offlinemind.tools.file_tools import ReadFileTool, WriteFileTool, DeleteFileTool
from offlinemind.tools.system_tools import SystemInfoTool

logger = logging.getLogger(__name__)


class ToolManager:
    """Registers tools, validates arguments, enforces permission checks, and executes actions."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.register(CalculatorTool())
        self.register(SystemInfoTool())
        self.register(ReadFileTool())
        self.register(WriteFileTool())
        self.register(DeleteFileTool())

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns catalog of available tools."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "is_dangerous": t.is_dangerous,
            }
            for t in self._tools.values()
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any], user_confirmed: bool = False) -> ToolResult:
        """Validates and executes a tool."""
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(success=False, output=None, error=f"Unknown tool: '{tool_name}'")

        if tool.is_dangerous and not user_confirmed:
            return ToolResult(
                success=False,
                output=None,
                requires_confirmation=True,
                confirmation_prompt=f"Executing tool '{tool.name}' requires explicit user confirmation.",
            )

        try:
            return tool.execute(user_confirmed=user_confirmed, **arguments)
        except Exception as e:
            logger.error("Error executing tool '%s': %s", tool_name, e)
            return ToolResult(success=False, output=None, error=str(e))
