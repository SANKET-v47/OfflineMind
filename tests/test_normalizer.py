"""Unit tests for QueryNormalizer."""

import pytest
from offlinemind.web.normalizer import QueryNormalizer


def test_normalizer_typo_correction():
    normalizer = QueryNormalizer()

    # User's exact prompt typo
    norm, corrs = normalizer.normalize("who is curret Ceo of google")
    assert "current" in norm
    assert "CEO" in norm
    assert "curret" in corrs
    assert corrs["curret"] == "current"

    norm2, corrs2 = normalizer.normalize("curret ceo")
    assert norm2 == "current CEO"

    norm3, _ = normalizer.normalize("presdent of us")
    assert "president" in norm3

    norm4, _ = normalizer.normalize("wether today")
    assert "weather" in norm4


def test_normalizer_difflib_matching():
    normalizer = QueryNormalizer()

    # Close misspellings
    result, corrs = normalizer.normalize("googl stock price")
    assert "Google" in result or "google" in result.lower()

    result2, _ = normalizer.normalize("whather in tokyo")
    assert "weather" in result2.lower()


def test_normalizer_preserves_clean_queries():
    normalizer = QueryNormalizer()
    query = "What is the capital of France?"
    result, corrs = normalizer.normalize(query)
    assert result == query
    assert len(corrs) == 0
