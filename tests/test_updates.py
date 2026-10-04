"""Unit tests for Phase 8: Application, Model, and Knowledge Updaters."""

from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path
import pytest

from offlinemind.updates.update_manager import (
    AppUpdateChecker,
    ModelUpdateChecker,
    KnowledgeUpdater,
)
from offlinemind.web.search import MockSearchProvider
from offlinemind.rag.vector_store import LocalVectorStore


def test_app_update_checker_no_update():
    checker = AppUpdateChecker(current_version="1.0.0")
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"tag_name": "v1.0.0", "body": "Release v1.0.0", "html_url": "https://github.com"}
        )
        res = checker.check_for_updates()
        assert res["has_update"] is False
        assert res["current_version"] == "1.0.0"


def test_app_update_checker_with_update():
    checker = AppUpdateChecker(current_version="1.0.0")
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"tag_name": "v1.1.0", "body": "New feature release", "html_url": "https://github.com/release"}
        )
        res = checker.check_for_updates()
        assert res["has_update"] is True
        assert res["latest_version"] == "1.1.0"


def test_model_update_catalog_and_proposal():
    catalog = ModelUpdateChecker.get_model_catalog()
    assert "llama3.2:1b" in catalog
    assert "llama3.2:3b" in catalog
    assert catalog["llama3.2:3b"]["size_gb"] == 2.0

    proposal = ModelUpdateChecker.prepare_upgrade_proposal("llama3.2:1b", "llama3.2:3b")
    assert proposal["requires_user_approval"] is True
    assert proposal["target_model"] == "llama3.2:3b"


def test_knowledge_updater_ingests_to_vector_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "rag_updates.db"
        store = LocalVectorStore(db_path=db_path)
        search_provider = MockSearchProvider()

        updater = KnowledgeUpdater(search_provider=search_provider, vector_store=store)
        res = updater.update_knowledge("Python 3.14 features", max_sources=1)

        assert res["success"] is True
        assert res["sources_added"] == 1

        docs = store.list_documents()
        assert len(docs) == 1
        assert "Python" in docs[0]["name"] or "tmp" in docs[0]["name"]
