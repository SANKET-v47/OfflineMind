"""Unit tests for Phase 5: Structured Memory System."""

import tempfile
from pathlib import Path
import pytest
from offlinemind.memory.memory_manager import MemoryManager


def test_short_term_memory():
    with tempfile.TemporaryDirectory() as tmpdir:
        mm = MemoryManager(memory_dir=tmpdir, max_short_term_turns=3)
        mm.add_turn("user", "Hello")
        mm.add_turn("assistant", "Hi there!")

        ctx = mm.get_conversation_context()
        assert len(ctx) == 2
        assert ctx[0]["role"] == "user"
        assert ctx[1]["content"] == "Hi there!"

        # Clear short term
        mm.clear_short_term()
        assert len(mm.get_conversation_context()) == 0


def test_long_term_facts_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        mm = MemoryManager(memory_dir=tmpdir)
        mm.remember_fact("user_name", "Sanket")
        mm.remember_fact("favorite_language", "Python")

        assert mm.get_all_facts()["user_name"] == "Sanket"

        # Re-instantiate from same directory to verify persistence
        mm2 = MemoryManager(memory_dir=tmpdir)
        assert mm2.get_all_facts()["user_name"] == "Sanket"
        assert mm2.get_all_facts()["favorite_language"] == "Python"

        # Forget fact
        assert mm2.forget_fact("favorite_language") is True
        assert "favorite_language" not in mm2.get_all_facts()


def test_memory_export_and_import():
    with tempfile.TemporaryDirectory() as tmpdir:
        mm = MemoryManager(memory_dir=tmpdir)
        mm.remember_fact("topic", "AI Systems")
        export_file = Path(tmpdir) / "backup_memory.json"
        mm.export_memory(export_file)
        assert export_file.exists()

        # Wipe and import back
        mm.clear_all_memory()
        assert len(mm.get_all_facts()) == 0

        mm.import_memory(export_file)
        assert mm.get_all_facts()["topic"] == "AI Systems"
