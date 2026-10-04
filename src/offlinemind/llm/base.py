"""Abstract base class and contract for all LLM Providers."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterator, List, Optional, Dict, Any


class LLMProvider(ABC):
    """Abstract interface for local and external language model providers."""

    def __init__(self, model_name: str, timeout: float = 60.0):
        self.model_name = model_name
        self.timeout = timeout

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns unique identifier for this provider (e.g. 'ollama', 'gguf')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if provider backend is reachable and ready to serve."""
        pass

    @abstractmethod
    def list_models(self) -> List[str]:
        """Returns list of models installed/available locally."""
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """Executes full non-streaming generation and returns the generated text."""
        pass

    @abstractmethod
    def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Streams generated tokens/chunks in real time."""
        pass

    def pre_warm(self) -> bool:
        """Pre-loads the model weights into memory to eliminate cold-start latency."""
        return True
