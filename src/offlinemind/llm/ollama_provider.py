"""Ollama Local LLM Provider implementation with streaming and pre-warming."""

from __future__ import annotations
import json
import logging
import socket
from typing import Iterator, List, Optional, Any
from urllib.parse import urlparse
import requests

from offlinemind.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Local LLM Provider utilizing Ollama HTTP daemon."""

    def __init__(
        self,
        model_name: str = "llama3.2:1b",
        base_url: str = "http://localhost:11434",
        timeout: float = 60.0,
    ):
        super().__init__(model_name=model_name, timeout=timeout)
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _is_server_reachable(self) -> bool:
        """Fast socket probe checking if Ollama port is open (<0.2s)."""
        try:
            parsed = urlparse(self.base_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 11434
            with socket.create_connection((host, port), timeout=0.25):
                return True
        except Exception:
            return False

    def is_available(self) -> bool:
        """Verifies Ollama daemon is running and has at least one model."""
        if not self._is_server_reachable():
            return False
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                models = self.list_models()
                if models:
                    # Auto-fallback to available model if configured model is absent
                    model_base = self.model_name.split(":")[0]
                    if not any(model_base in m for m in models):
                        self.model_name = models[0]
                    return True
        except Exception as e:
            logger.debug("Ollama is_available probe failed: %s", e)
        return False

    def list_models(self) -> List[str]:
        """Fetches list of all installed local models."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            logger.debug("Failed to list Ollama models: %s", e)
        return []

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """Executes non-streaming generation."""
        opts = {"temperature": temperature, "top_p": 0.9, "repeat_penalty": 1.15}
        opts.update(kwargs)
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": opts,
        }
        if system_prompt:
            payload["system"] = system_prompt

        resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        raise RuntimeError(f"Ollama generation failed (HTTP {resp.status_code}): {resp.text}")

    def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Streams generated tokens in real time directly from Ollama."""
        opts = {"temperature": temperature, "top_p": 0.9, "repeat_penalty": 1.15}
        opts.update(kwargs)
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": True,
            "options": opts,
        }
        if system_prompt:
            payload["system"] = system_prompt

        resp = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            stream=True,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama stream failed (HTTP {resp.status_code}): {resp.text}")

        for line in resp.iter_lines():
            if line:
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    text = chunk.get("response", "")
                    if text:
                        yield text
                    if chunk.get("done", False):
                        break
                except Exception as e:
                    logger.debug("Error parsing stream chunk: %s", e)

    def pre_warm(self) -> bool:
        """Pre-warms the model into memory asynchronously to prevent first-query lag."""
        try:
            logger.info("Pre-warming model '%s' in Ollama...", self.model_name)
            payload = {
                "model": self.model_name,
                "prompt": "hi",
                "stream": False,
                "options": {"num_predict": 1},
            }
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Pre-warm request skipped or failed: %s", e)
            return False
