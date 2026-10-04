"""Smart Intent Query Router distinguishing local reasoning, web search, documents, and tools."""

from __future__ import annotations
import enum
import re
from typing import Dict, List, Optional, Set, Tuple


class RouteIntent(enum.Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    WEB_REQUIRED = "WEB_REQUIRED"
    WEB_OPTIONAL = "WEB_OPTIONAL"
    LOCAL_DOCUMENT_REQUIRED = "LOCAL_DOCUMENT_REQUIRED"
    TOOL_REQUIRED = "TOOL_REQUIRED"


from offlinemind.web.normalizer import QueryNormalizer


class QueryRouter:
    """Classifies user queries into optimal routing strategies."""

    # Keywords strictly requiring live internet intelligence
    WEB_KEYWORDS: Set[str] = {
        "today", "current", "currently", "latest", "recent", "recently", "news",
        "weather", "forecast", "stock", "stocks", "ticker", "price of",
        "announcement", "released", "release notes", "who won", "breaking",
        "right now", "update on", "live", "trending", "score", "scores",
    }

    # Document-related cues
    DOCUMENT_KEYWORDS: Set[str] = {
        "pdf", "docx", "document", "this file", "my notes", "summarize file",
        "attached", "uploaded", "read file", "parse file",
    }

    # Tool-related cues
    TOOL_KEYWORDS: Set[str] = {
        "calculate", "run command", "create file", "delete file", "save to file",
        "open browser", "system info", "disk space", "math evaluate",
    }

    # Semantic entity & leadership patterns requiring live or verified lookup
    SEMANTIC_WEB_PATTERNS: List[str] = [
        r"\bwho (is|was|are|leads|runs|founded|heads)\b",
        r"\b(ceo|cto|cfo|president|prime minister|founder|chairman|owner|leader|head) of\b",
        r"\b(capital|population|net worth|gdp|price|stock price|founder|weather|score) of\b",
        r"\bwho won\b",
        r"\bwhen (is|was|will be|did)\b",
        r"\b(what is the|what's the) (price|cost|weather|forecast|score|capital)\b",
    ]

    @classmethod
    def route(cls, query: str, has_attached_docs: bool = False) -> Tuple[RouteIntent, str]:
        """Analyzes query and returns optimal RouteIntent and human-readable reasoning."""
        # Auto-correct typos first
        normalized_q, _ = QueryNormalizer.normalize(query)
        clean_q = normalized_q.strip().lower()
        words = set(re.findall(r"\w+", clean_q))

        # 1. Document ingestion / retrieval priority
        if has_attached_docs or any(kw in clean_q for kw in cls.DOCUMENT_KEYWORDS):
            return RouteIntent.LOCAL_DOCUMENT_REQUIRED, "Query targets local document or uploaded file."

        # 2. Tool execution priority
        if any(kw in clean_q for kw in cls.TOOL_KEYWORDS):
            return RouteIntent.TOOL_REQUIRED, "Query requires execution of a local tool or calculation."

        # 3. Semantic entity, role, or factual question patterns
        for pat in cls.SEMANTIC_WEB_PATTERNS:
            if re.search(pat, clean_q):
                return RouteIntent.WEB_REQUIRED, f"Query requests real-world entity/role/factual information (matched: {pat})."

        # 4. Time-sensitive / Current web information check (exact + fuzzy)
        matched_web_terms = words & cls.WEB_KEYWORDS or [kw for kw in cls.WEB_KEYWORDS if kw in clean_q]
        if matched_web_terms:
            return RouteIntent.WEB_REQUIRED, f"Query references time-sensitive content ({', '.join(matched_web_terms)})."

        # 5. Default: Local high-speed LLM generation & local fact store
        return RouteIntent.LOCAL_ONLY, "General query answered effectively by local neural weights and facts."
