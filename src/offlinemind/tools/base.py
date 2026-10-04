"""Tool base contract and execution results."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ToolResult:
    """Standardized output of a tool execution."""

    def __init__(
        self,
        success: bool,
        output: Any,
        error: Optional[str] = None,
        requires_confirmation: bool = False,
        confirmation_prompt: Optional[str] = None,
    ):
        self.success = success
        self.output = output
        self.error = error
        self.requires_confirmation = requires_confirmation
        self.confirmation_prompt = confirmation_prompt

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "requires_confirmation": self.requires_confirmation,
        }

    def __repr__(self) -> str:
        return f"<ToolResult success={self.success} output='{str(self.output)[:50]}'>"


class Tool(ABC):
    """Abstract interface for assistant-callable tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    def is_dangerous(self) -> bool:
        """Dangerous tools require explicit human confirmation before execution."""
        return False

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        pass
