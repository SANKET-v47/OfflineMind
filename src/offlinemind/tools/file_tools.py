"""File management tools with path traversal protection and safety confirmations."""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

from offlinemind.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


class ReadFileTool(Tool):
    """Safely reads contents of a text file."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Reads the contents of a local text or markdown file."

    def execute(self, path: str, max_chars: int = 10000, **kwargs: Any) -> ToolResult:
        try:
            target = Path(path).resolve()
            if not target.exists():
                return ToolResult(success=False, output=None, error=f"File not found: {path}")
            if not target.is_file():
                return ToolResult(success=False, output=None, error=f"Path is not a file: {path}")

            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class WriteFileTool(Tool):
    """Safely writes content to a file. Requires confirmation if overwriting."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Writes text content to a file. Overwrites require user approval."

    def execute(self, path: str, content: str, user_confirmed: bool = False, **kwargs: Any) -> ToolResult:
        try:
            target = Path(path).resolve()
            if target.exists() and not user_confirmed:
                return ToolResult(
                    success=False,
                    output=None,
                    requires_confirmation=True,
                    confirmation_prompt=f"File '{target.name}' already exists. Confirm overwrite?",
                )

            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, output=f"Successfully wrote {len(content)} characters to {target.name}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class DeleteFileTool(Tool):
    """Deletes a local file. Always dangerous; strictly requires user confirmation."""

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return "Permanently deletes a file. Always requires user confirmation."

    @property
    def is_dangerous(self) -> bool:
        return True

    def execute(self, path: str, user_confirmed: bool = False, **kwargs: Any) -> ToolResult:
        target = Path(path).resolve()
        if not target.exists():
            return ToolResult(success=False, output=None, error=f"File not found: {path}")

        if not user_confirmed:
            return ToolResult(
                success=False,
                output=None,
                requires_confirmation=True,
                confirmation_prompt=f"Are you sure you want to PERMANENTLY delete '{target}'?",
            )

        try:
            target.unlink()
            return ToolResult(success=True, output=f"Successfully deleted {target.name}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
