"""Tests for the OfflineMind CLI commands."""

import argparse
from io import StringIO
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from offlinemind.ui.cli import cmd_status, cmd_query, cmd_add_fact, cmd_history, cmd_sync
from offlinemind.db.connection import DatabaseManager
from offlinemind.core.knowledge_engine import KnowledgeEngine


@pytest.fixture
def cli_test_env(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "cli_test.db"
        backup_dir = Path(tmpdir) / "backups"
        monkeypatch.setenv("OFFLINEMIND_DB_PATH", str(db_path))
        monkeypatch.setenv("OFFLINEMIND_BACKUP_DIR", str(backup_dir))

        db = DatabaseManager(db_path)
        ke = KnowledgeEngine(db)
        ke.add_fact("College", "name", "Springfield Tech", "Handbook", 50)
        yield db, ke
        db.close()


def test_cli_status(cli_test_env):
    output = StringIO()
    with patch("sys.stdout", output):
        cmd_status(None)
    text = output.getvalue()
    assert "OfflineMind System Status" in text
    assert "Active Facts Stored" in text


def test_cli_query(cli_test_env):
    output = StringIO()
    args = argparse.Namespace(query="What is my college name?", provenance=True)
    with patch("sys.stdout", output):
        cmd_query(args)
    text = output.getvalue()
    assert "Springfield Tech" in text
    assert "Provenance:" in text


def test_cli_add_fact(cli_test_env):
    args = argparse.Namespace(
        entity="Department",
        attribute="head",
        value="Dr. Clark",
        source="Catalog",
        priority=60,
        category="academic",
    )
    cmd_add_fact(args)
    from offlinemind.ui.cli import init_system
    _, _, current_ke, _, _, _ = init_system()
    f = current_ke.get_fact("Department", "head")
    assert f is not None
    assert f.value == "Dr. Clark"


def test_cli_history(cli_test_env):
    output = StringIO()
    args = argparse.Namespace(entity="College", attribute="name")
    with patch("sys.stdout", output):
        cmd_history(args)
    text = output.getvalue()
    assert "Audit History Trail" in text
    assert "Springfield Tech" in text


def test_interactive_repl_commands(cli_test_env):
    from offlinemind.ui.cli import interactive_repl

    user_inputs = iter([":web off", ":help", ":clear", ":memory", ":docs", ":quit"])
    output = StringIO()

    with patch("builtins.input", side_effect=lambda prompt="": next(user_inputs)), \
         patch("sys.stdout", output):
        interactive_repl()

    out_text = output.getvalue()
    assert "Web intelligence disabled" in out_text
    assert "Available commands" in out_text
    assert "Conversation context cleared" in out_text
    assert "Goodbye!" in out_text

