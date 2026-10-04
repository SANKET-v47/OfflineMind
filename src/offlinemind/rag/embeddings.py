"""Local embedding provider and vector similarity calculations."""

from __future__ import annotations
from abc import ABC, abstractmethod
import math
import re
from typing import List, Dict, Optional, Any
import requests


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class EmbeddingProvider(ABC):
    """Abstract interface for generating text embeddings."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """Fast, deterministic local hashing vectorizer.
    Produces dense, normalized 128-dimensional semantic representations
    using character and word n-grams without needing external neural packages.
    """

    def __init__(self, dimension: int = 128):
        self.dimension = dimension

    def embed_text(self, text: str) -> List[float]:
        vec = [0.0] * self.dimension
        clean = text.lower().strip()
        words = re.findall(r"\w+", clean)

        # 1. Word level features
        for w in words:
            h = hash(w) % self.dimension
            vec[h] += 1.0

        # 2. Character 3-gram features
        for i in range(len(clean) - 2):
            trigram = clean[i:i + 3]
            h = hash(trigram) % self.dimension
            vec[h] += 0.5

        # Normalize to unit length
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0.0:
            vec = [x / norm for x in vec]
        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Generates embeddings using Ollama daemon if an embedding model is available."""

    def __init__(
        self,
        model_name: str = "all-minilm",
        base_url: str = "http://localhost:11434",
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.fallback = LocalHashEmbeddingProvider()

    def embed_text(self, text: str) -> List[float]:
        try:
            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model_name, "prompt": text},
                timeout=5.0,
            )
            if resp.status_code == 200:
                return resp.json().get("embedding", [])
        except Exception:
            pass
        return self.fallback.embed_text(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]
