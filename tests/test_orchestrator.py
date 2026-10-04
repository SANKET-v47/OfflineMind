"""Unit and integration tests for AssistantOrchestrator."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from offlinemind.core.orchestrator import AssistantOrchestrator
from offlinemind.llm.model_manager import ModelManager
from offlinemind.web.internet_manager import InternetManager, InternetState
from offlinemind.web.search import MockSearchProvider
from offlinemind.rag.vector_store import LocalVectorStore
from offlinemind.memory.memory_manager import MemoryManager
from offlinemind.tools.manager import ToolManager


def test_orchestrator_local_query_stream():
    with tempfile.TemporaryDirectory() as tmpdir:
        vec_store = LocalVectorStore(Path(tmpdir) / "rag.db")
        mem_mgr = MemoryManager(Path(tmpdir) / "mem")
        tool_mgr = ToolManager()
        search_prov = MockSearchProvider()
        net_mgr = InternetManager(check_interval=0.1, probe_timeout=0.1)

        # Mock LLM provider
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.stream_generate.return_value = ["Recursion ", "is ", "a ", "method."]

        model_mgr = MagicMock()
        model_mgr.active_provider = mock_provider

        orch = AssistantOrchestrator(
            model_manager=model_mgr,
            internet_manager=net_mgr,
            search_provider=search_prov,
            vector_store=vec_store,
            memory_manager=mem_mgr,
            tool_manager=tool_mgr,
        )

        tokens = list(orch.process_query_stream("Explain recursion"))
        assert "".join(tokens) == "Recursion is a method."
        assert len(mem_mgr.get_conversation_context()) == 2


def test_orchestrator_tool_calculation():
    with tempfile.TemporaryDirectory() as tmpdir:
        mem_mgr = MemoryManager(Path(tmpdir) / "mem")
        orch = AssistantOrchestrator(memory_manager=mem_mgr)

        tokens = list(orch.process_query_stream("calculate 15 * 4 + 10"))
        reply = "".join(tokens)
        assert "70" in reply
        assert "Calculation Result" in reply


def test_orchestrator_remember_command():
    with tempfile.TemporaryDirectory() as tmpdir:
        mem_mgr = MemoryManager(Path(tmpdir) / "mem")
        orch = AssistantOrchestrator(memory_manager=mem_mgr)

        tokens = list(orch.process_query_stream("remember that my dog is named Milo"))
        reply = "".join(tokens)
        assert "committed this to my local long-term memory" in reply
        assert any("Milo" in str(v) for v in mem_mgr.get_all_facts().values())


def test_orchestrator_web_query_when_offline():
    with tempfile.TemporaryDirectory() as tmpdir:
        net_mgr = InternetManager()
        net_mgr.set_force_offline(True)  # Force offline

        # Mock LLM
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.stream_generate.return_value = ["AI ", "is ", "evolving."]

        model_mgr = MagicMock()
        model_mgr.active_provider = mock_provider

        orch = AssistantOrchestrator(
            model_manager=model_mgr,
            internet_manager=net_mgr,
            memory_manager=MemoryManager(Path(tmpdir) / "mem"),
        )

        tokens = list(orch.process_query_stream("What is the latest AI news today?"))
        reply = "".join(tokens)
        # Must clearly indicate offline notice
        assert "Offline Mode Notice" in reply
        assert "cannot verify today's information" in reply
