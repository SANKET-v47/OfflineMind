"""Unit tests for Phase 7: Security Guardrails, Sandboxing, and Safe Protocols."""

import pytest
from offlinemind.sync.validator import validate_sync_url
from offlinemind.tools.file_tools import DeleteFileTool, WriteFileTool
from offlinemind.tools.calculator import CalculatorTool


def test_url_protocol_guardrails():
    # Dangerous schemes strictly rejected
    assert validate_sync_url("file:///C:/Windows/System32/cmd.exe") is False
    assert validate_sync_url("javascript:alert(1)") is False
    assert validate_sync_url("data:text/html;base64,PHNjcmlwdD4=") is False
    assert validate_sync_url("ftp://malicious.org/feed.json") is False

    # Safe web protocols accepted
    assert validate_sync_url("https://trusted.university.edu/feed.json") is True


def test_shell_injection_prevention_in_calculator():
    calc = CalculatorTool()
    malicious_inputs = [
        "import os; os.system('calc')",
        "__builtins__.__import__('subprocess').run(['calc'])",
        "eval('1 + 1')",
        "exec('print(1)')",
    ]
    for m in malicious_inputs:
        res = calc.execute(m)
        assert res.success is False
        assert res.output is None


def test_unauthorized_deletion_blocked():
    deleter = DeleteFileTool()
    res = deleter.execute(path="C:/important_doc.pdf", user_confirmed=False)
    # Must fail or require user confirmation
    assert res.requires_confirmation is True or res.success is False
