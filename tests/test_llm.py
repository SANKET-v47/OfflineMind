"""Unit tests for the LLM Service and fallback answering."""

from unittest.mock import patch, MagicMock
import pytest
from offlinemind.core.models import Fact, FactHistoryEntry, SearchResult
from offlinemind.llm.llm_client import LLMService


@pytest.fixture
def sample_fact():
    return Fact(
        entity="College",
        attribute="name",
        value="Springfield Institute of Technology",
        source="Registrar Portal",
        source_priority=80,
        version=2,
        updated_at="2026-03-15T12:00:00Z",
    )


@pytest.fixture
def sample_history():
    return [
        FactHistoryEntry(
            fact_id="f1",
            entity="College",
            attribute="name",
            old_value="Springfield Community College",
            new_value="Springfield Institute of Technology",
            source="University Board Gazette",
            version=1,
            change_reason="Official charter upgrade",
            timestamp="2026-03-15T12:00:00Z",
        )
    ]


def test_fallback_extractive_answer_with_history(sample_fact, sample_history):
    llm = LLMService(base_url="http://invalid-ollama-host:11434")
    # Should automatically fall back without throwing an error
    search_res = [SearchResult(fact=sample_fact, score=1.0, match_type="exact")]
    answer = llm.generate_answer(
        query="What is my college name?",
        search_results=search_res,
        history_entries=sample_history,
    )

    assert "Springfield Institute of Technology" in answer.text
    assert answer.model_used == "retrieval-extractive"
    assert answer.history_note is not None
    assert "Springfield Community College" in answer.history_note
    assert "University Board Gazette" in answer.history_note
    assert "Registrar Portal" in answer.provenance


def test_fallback_extractive_answer_no_results():
    llm = LLMService()
    answer = llm.generate_answer(query="What is the speed of light?", search_results=[])
    assert "do not have verified knowledge" in answer.text
    assert answer.confidence == 0.0


def test_provenance_flag_in_query(sample_fact):
    llm = LLMService()
    search_res = [SearchResult(fact=sample_fact, score=1.0, match_type="exact")]
    answer = llm.generate_answer(
        query="What is my college name? Include provenance",
        search_results=search_res,
    )
    assert "**Provenance:**" in answer.text
    assert "Registrar Portal" in answer.text


def test_mocked_ollama_call(sample_fact, sample_history):
    llm = LLMService()

    mock_resp_tags = MagicMock()
    mock_resp_tags.status_code = 200
    mock_resp_tags.json.return_value = {"models": [{"name": "phi3:mini"}]}

    mock_resp_gen = MagicMock()
    mock_resp_gen.status_code = 200
    mock_resp_gen.json.return_value = {
        "response": "Your college is now known as Springfield Institute of Technology."
    }

    with patch.object(llm, "_is_server_reachable", return_value=True), \
         patch("requests.get", return_value=mock_resp_tags), \
         patch("requests.post", return_value=mock_resp_gen):
        search_res = [SearchResult(fact=sample_fact, score=1.0, match_type="exact")]
        answer = llm.generate_answer(
            query="What is my college name?",
            search_results=search_res,
            history_entries=sample_history,
        )
        assert answer.model_used.startswith("ollama:")
        assert "Springfield Institute of Technology" in answer.text
