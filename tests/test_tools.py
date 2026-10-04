"""Unit tests for Phase 6: Tool Execution and Safety Checks."""

import tempfile
from pathlib import Path
import pytest

from offlinemind.tools.calculator import CalculatorTool
from offlinemind.tools.system_tools import SystemInfoTool
from offlinemind.tools.file_tools import ReadFileTool, WriteFileTool, DeleteFileTool
from offlinemind.tools.manager import ToolManager


def test_calculator_tool_safety():
    calc = CalculatorTool()
    # Basic math
    res = calc.execute("2 + 2 * 10")
    assert res.success is True
    assert res.output == 22

    # Advanced safe functions
    res2 = calc.execute("sqrt(144) + sin(0)")
    assert res2.success is True
    assert res2.output == 12.0

    # Arbitrary code execution blocked
    res_bad = calc.execute("__import__('os').system('dir')")
    assert res_bad.success is False
    assert "error" in res_bad.error.lower()


def test_system_info_tool():
    sys_tool = SystemInfoTool()
    res = sys_tool.execute()
    assert res.success is True
    assert "os" in res.output
    assert "disk_total_gb" in res.output
    assert res.output["disk_total_gb"] > 0


def test_file_tools_and_confirmation():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "notes.txt"

        writer = WriteFileTool()
        reader = ReadFileTool()
        deleter = DeleteFileTool()

        # Write new file (no overwrite)
        res_write = writer.execute(path=str(test_file), content="Secret offline notes")
        assert res_write.success is True
        assert test_file.exists()

        # Overwrite requires confirmation
        res_overwrite_blocked = writer.execute(path=str(test_file), content="New notes", user_confirmed=False)
        assert res_overwrite_blocked.requires_confirmation is True

        # Overwrite with confirmation
        res_overwrite_ok = writer.execute(path=str(test_file), content="New notes", user_confirmed=True)
        assert res_overwrite_ok.success is True

        # Read
        res_read = reader.execute(path=str(test_file))
        assert res_read.success is True
        assert res_read.output == "New notes"

        # Delete blocked without confirmation
        res_del_blocked = deleter.execute(path=str(test_file), user_confirmed=False)
        assert res_del_blocked.requires_confirmation is True
        assert test_file.exists()

        # Delete permitted with confirmation
        res_del_ok = deleter.execute(path=str(test_file), user_confirmed=True)
        assert res_del_ok.success is True
        assert not test_file.exists()


def test_tool_manager_dispatch():
    tm = ToolManager()
    tools = tm.list_tools()
    tool_names = [t["name"] for t in tools]
    assert "calculator" in tool_names
    assert "system_info" in tool_names
    assert "delete_file" in tool_names

    # Unknown tool
    res = tm.execute("magic_wand", {})
    assert res.success is False
    assert "Unknown tool" in res.error
