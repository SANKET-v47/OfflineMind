"""Intelligent query normalizer: auto-corrects typos, fixes slang, and resolves semantics."""

from __future__ import annotations
import difflib
import re
from typing import Dict, List, Optional, Set, Tuple


class QueryNormalizer:
    """Auto-corrects user input typos and normalizes semantic queries."""

    # Common typographical errors and phonetic misspellings
    COMMON_TYPOS: Dict[str, str] = {
        # Current / Temporal
        "curret": "current",
        "curren": "current",
        "curent": "current",
        "crrent": "current",
        "currnt": "current",
        "latst": "latest",
        "lastest": "latest",
        "laytest": "latest",
        "todai": "today",
        "tday": "today",
        "recnt": "recent",
        "recentley": "recently",
        "weathr": "weather",
        "wether": "weather",
        "weater": "weather",
        "newz": "news",

        # Common Question Starters & Contractions
        "whos": "who is",
        "who's": "who is",
        "whats": "what is",
        "what's": "what is",
        "wht": "what",
        "wat": "what",
        "hwo": "how",
        "hw": "how",
        "wen": "when",
        "wer": "where",
        "whr": "where",
        "abt": "about",
        "plz": "please",
        "pls": "please",
        "thx": "thanks",
        "u": "you",
        "ur": "your",

        # Roles & Entities
        "ceo": "CEO",
        "ceos": "CEOs",
        "cto": "CTO",
        "cfo": "CFO",
        "presidnet": "president",
        "presdent": "president",
        "presedent": "president",
        "minstr": "minister",
        "minisetr": "minister",
        "primeminister": "prime minister",

        # Tech & Organizations
        "googl": "Google",
        "gogle": "Google",
        "microsft": "Microsoft",
        "mircosoft": "Microsoft",
        "opena": "OpenAI",
        "open-ai": "OpenAI",
        "tesl": "Tesla",
        "amzon": "Amazon",
        "nvdia": "Nvidia",

        # Technical Vocabulary
        "algrithm": "algorithm",
        "algoritm": "algorithm",
        "progamming": "programming",
        "programing": "programming",
        "langauge": "language",
        "languege": "language",
        "defination": "definition",
        "explian": "explain",
        "diffrence": "difference",
        "recursiv": "recursive",
        "funtion": "function",
        "calcualte": "calculate",
        "claculate": "calculate",
    }

    # Reference vocabulary for fuzzy matching
    REFERENCE_VOCABULARY: Set[str] = {
        "current", "currently", "latest", "recent", "recently", "today", "yesterday",
        "tomorrow", "weather", "forecast", "news", "president", "minister", "governor",
        "founder", "executive", "director", "chairman", "stock", "price", "market",
        "release", "released", "announcement", "champion", "winner", "score",
        "calculate", "explain", "summarize", "difference", "compare", "programming",
        "algorithm", "function", "language", "hardware", "software", "database",
        "google", "microsoft", "apple", "amazon", "tesla", "openai", "meta", "nvidia",
    }

    @classmethod
    def normalize(cls, query: str) -> Tuple[str, Dict[str, str]]:
        """Normalizes query by fixing typos, contractions, and spacing.
        
        Returns:
            (normalized_query, corrections_applied)
        """
        raw = query.strip()
        if not raw:
            return "", {}

        # 1. Standardize spacing and basic punctuation
        cleaned = re.sub(r"\s+", " ", raw)

        words = cleaned.split()
        normalized_words: List[str] = []
        corrections: Dict[str, str] = {}

        for word in words:
            # Strip trailing punctuation for dictionary check
            match = re.match(r"^([^\w]*)([\w'-]+)([^\w]*)$", word)
            if not match:
                normalized_words.append(word)
                continue

            prefix, core, suffix = match.groups()
            lower_core = core.lower()

            # Check direct typo dictionary
            if lower_core in cls.COMMON_TYPOS:
                replacement = cls.COMMON_TYPOS[lower_core]
                corrections[core] = replacement
                normalized_words.append(f"{prefix}{replacement}{suffix}")
                continue

            # Check fuzzy match against reference vocabulary if length >= 4
            if len(lower_core) >= 4 and not lower_core.isdigit():
                close_matches = difflib.get_close_matches(lower_core, cls.REFERENCE_VOCABULARY, n=1, cutoff=0.82)
                if close_matches and close_matches[0] != lower_core:
                    replacement = close_matches[0]
                    # Preserve capitalization if original was capitalized
                    if core.istitle():
                        replacement = replacement.title()
                    corrections[core] = replacement
                    normalized_words.append(f"{prefix}{replacement}{suffix}")
                    continue

            normalized_words.append(word)

        normalized_query = " ".join(normalized_words)
        return normalized_query, corrections
