"""Model Manager factory orchestrating LLM providers, model detection, and switching."""

from __future__ import annotations
import logging
import threading
from typing import Dict, List, Optional, Type, Any

from offlinemind.config import MODEL_PROVIDER, MODEL_NAME, OLLAMA_BASE_URL, OLLAMA_TIMEOUT_SEC
from offlinemind.llm.base import LLMProvider
from offlinemind.llm.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


class ModelManager:
    """Factory and registry for local LLM providers."""

    _REGISTRY: Dict[str, Type[LLMProvider]] = {
        "ollama": OllamaProvider,
    }

    def __init__(
        self,
        default_provider: str = MODEL_PROVIDER,
        default_model: str = MODEL_NAME,
        timeout: float = OLLAMA_TIMEOUT_SEC,
    ):
        self.default_provider_name = default_provider.lower()
        self.default_model_name = default_model
        self.timeout = timeout
        self._active_provider: Optional[LLMProvider] = None
        self._init_provider()

    def _init_provider(self) -> None:
        """Initializes the active provider instance."""
        provider_cls = self._REGISTRY.get(self.default_provider_name, OllamaProvider)
        if provider_cls is OllamaProvider:
            chosen_model = self.default_model_name
            try:
                temp_prov = OllamaProvider(model_name="probe", base_url=OLLAMA_BASE_URL, timeout=2.0)
                installed = temp_prov.list_models()
                if self.default_model_name in installed:
                    chosen_model = self.default_model_name
                else:
                    for preferred in ["llama3.2:3b", "mistral:7b", "phi3:mini", "llama3.2:1b"]:
                        if any(preferred in m for m in installed):
                            chosen_model = next(m for m in installed if preferred in m)
                            break
                    else:
                        if installed:
                            chosen_model = installed[0]
            except Exception as e:
                logger.debug("Model auto-detection skipped: %s", e)

            self._active_provider = OllamaProvider(
                model_name=chosen_model,
                base_url=OLLAMA_BASE_URL,
                timeout=self.timeout,
            )
        else:
            self._active_provider = provider_cls(model_name=self.default_model_name, timeout=self.timeout)

        # Trigger non-blocking pre-warm in background thread
        threading.Thread(target=self._pre_warm_async, daemon=True).start()

    def _pre_warm_async(self) -> None:
        if self._active_provider and self._active_provider.is_available():
            self._active_provider.pre_warm()

    @property
    def active_provider(self) -> LLMProvider:
        if self._active_provider is None:
            self._init_provider()
        assert self._active_provider is not None
        return self._active_provider

    def switch_model(self, model_name: str) -> bool:
        """Dynamically switches active model."""
        self.default_model_name = model_name
        self.active_provider.model_name = model_name
        logger.info("Switched active model to '%s'", model_name)
        return True

    @property
    def active_model(self) -> str:
        """Returns the active model name."""
        return self.active_provider.model_name

    def get_best_available_model(self) -> str:
        """Returns the best available model detected on system."""
        return self.active_provider.model_name

    def get_status(self) -> Dict[str, Any]:
        """Returns health diagnostic information for active provider."""
        provider = self.active_provider
        available = provider.is_available()
        models = provider.list_models() if available else []
        return {
            "provider": provider.provider_name,
            "configured_model": provider.model_name,
            "is_available": available,
            "installed_models": models,
            "setup_guide": (
                "" if available and models else
                "Local model runtime not active. Run 'ollama run llama3.2:1b' to start your local AI."
            ),
        }
