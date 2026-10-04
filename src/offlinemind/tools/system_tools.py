"""Safe read-only system inspection tools."""

from __future__ import annotations
import os
import platform
import shutil
from typing import Any, Dict

from offlinemind.tools.base import Tool, ToolResult


class SystemInfoTool(Tool):
    """Provides hardware and operational diagnostics without invoking external shells."""

    @property
    def name(self) -> str:
        return "system_info"

    @property
    def description(self) -> str:
        return "Retrieves CPU architecture, OS platform, memory, and disk capacity."

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            total, used, free = shutil.disk_usage("C:\\" if os.name == "nt" else "/")
            info: Dict[str, Any] = {
                "os": platform.system(),
                "os_release": platform.release(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "disk_total_gb": round(total / (1024**3), 2),
                "disk_free_gb": round(free / (1024**3), 2),
                "disk_used_percent": round((used / total) * 100, 1),
            }
            return ToolResult(success=True, output=info)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
