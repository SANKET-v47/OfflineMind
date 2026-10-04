"""Safe, user-approved update system for application, knowledge, and models."""

from __future__ import annotations
import json
import logging
from typing import Dict, List, Optional, Any
import requests

from offlinemind.web.internet_manager import InternetManager
from offlinemind.web.search import WebSearchProvider
from offlinemind.rag.vector_store import LocalVectorStore

logger = logging.getLogger(__name__)

CURRENT_APP_VERSION = "1.0.0"


class AppUpdateChecker:
    """Checks for application updates with explicit user confirmation."""

    def __init__(self, current_version: str = CURRENT_APP_VERSION):
        self.current_version = current_version

    def check_for_updates(self, repo_url: str = "https://api.github.com/repos/SANKET-v47/OfflineMind/releases/latest") -> Dict[str, Any]:
        try:
            resp = requests.get(repo_url, timeout=4.0)
            if resp.status_code == 200:
                data = resp.json()
                tag = data.get("tag_name", "").lstrip("v")
                has_update = tag > self.current_version
                return {
                    "has_update": has_update,
                    "current_version": self.current_version,
                    "latest_version": tag,
                    "release_notes": data.get("body", "No release notes provided."),
                    "download_url": data.get("html_url", ""),
                }
        except Exception as e:
            logger.debug("Failed to check app updates: %s", e)

        return {
            "has_update": False,
            "current_version": self.current_version,
            "latest_version": self.current_version,
            "release_notes": "Up to date or offline.",
            "download_url": "",
        }


class ModelUpdateChecker:
    """Audits local models and inspects catalog for recommended upgrades. Never silently downloads."""

    RECOMMENDED_MODELS: Dict[str, Dict[str, Any]] = {
        "llama3.2:1b": {
            "size_gb": 1.3,
            "ram_required_gb": 4.0,
            "description": "Ultra-fast low-latency local model. Ideal for older hardware and quick chat.",
        },
        "llama3.2:3b": {
            "size_gb": 2.0,
            "ram_required_gb": 8.0,
            "description": "High conversational intelligence, excellent code generation and summarization.",
        },
        "phi3:mini": {
            "size_gb": 2.2,
            "ram_required_gb": 8.0,
            "description": "Microsoft's 3.8B model with strong mathematical and logical reasoning.",
        },
        "qwen2.5:1.5b": {
            "size_gb": 1.0,
            "ram_required_gb": 4.0,
            "description": "Compact multilingual model with rapid generation speeds.",
        },
    }

    @classmethod
    def get_model_catalog(cls) -> Dict[str, Dict[str, Any]]:
        return dict(cls.RECOMMENDED_MODELS)

    @classmethod
    def prepare_upgrade_proposal(cls, current_model: str, target_model: str) -> Dict[str, Any]:
        target_info = cls.RECOMMENDED_MODELS.get(target_model, {})
        return {
            "current_model": current_model,
            "target_model": target_model,
            "size_gb": target_info.get("size_gb", "Unknown"),
            "ram_required_gb": target_info.get("ram_required_gb", "Unknown"),
            "description": target_info.get("description", "Custom local model."),
            "requires_user_approval": True,
        }


class KnowledgeUpdater:
    """Selectively searches trusted web sources for a user topic and ingests facts into RAG."""

    def __init__(self, search_provider: WebSearchProvider, vector_store: LocalVectorStore):
        self.search_provider = search_provider
        self.vector_store = vector_store

    def update_knowledge(self, topic: str, max_sources: int = 3) -> Dict[str, Any]:
        """Searches the web for topic, fetches clean content, and saves to local vector database."""
        results = self.search_provider.search(topic, max_results=max_sources)
        if not results:
            return {"success": False, "sources_added": 0, "topic": topic}

        ingested = 0
        import tempfile
        from pathlib import Path

        for item in results:
            content = self.search_provider.fetch_page(item.url)
            if content and len(content.strip()) >= 20:
                with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
                    tmp.write(f"Source URL: {item.url}\nTitle: {item.title}\n\n{content}")
                    tmp_path = Path(tmp.name)
                try:
                    self.vector_store.add_document(
                        tmp_path,
                        metadata={
                            "title": item.title,
                            "url": item.url,
                            "topic": topic,
                            "type": "web_ingestion",
                        }
                    )
                    ingested += 1
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()

        return {
            "success": ingested > 0,
            "sources_added": ingested,
            "topic": topic,
        }
