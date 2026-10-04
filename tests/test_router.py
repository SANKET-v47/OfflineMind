"""Unit tests for QueryRouter."""

import pytest
from offlinemind.web.router import QueryRouter, RouteIntent


def test_router_local_only():
    queries = [
        "What is Python?",
        "Explain recursion.",
        "Write a Python class for binary search.",
        "Who created Linux?",
        "What is my college name?",
    ]
    for q in queries:
        intent, reason = QueryRouter.route(q)
        assert intent == RouteIntent.LOCAL_ONLY, f"Failed on: {q}"


def test_router_web_required():
    queries = [
        "What is today's weather in Tokyo?",
        "What are today's AI news?",
        "What happened in the latest OpenAI announcement?",
        "What is the current stock price of Apple?",
        "Who won the match yesterday?",
    ]
    for q in queries:
        intent, reason = QueryRouter.route(q)
        assert intent == RouteIntent.WEB_REQUIRED, f"Failed on: {q}"


def test_router_document_required():
    queries = [
        "Summarize this PDF on my desktop.",
        "Read this document and explain section 2.",
        "Analyze my notes file.",
    ]
    for q in queries:
        intent, reason = QueryRouter.route(q)
        assert intent == RouteIntent.LOCAL_DOCUMENT_REQUIRED, f"Failed on: {q}"


def test_router_tool_required():
    queries = [
        "Calculate 45 * 89 + 12",
        "Check my disk space",
        "Create file notes.txt with hello",
    ]
    for q in queries:
        intent, reason = QueryRouter.route(q)
        assert intent == RouteIntent.TOOL_REQUIRED, f"Failed on: {q}"
