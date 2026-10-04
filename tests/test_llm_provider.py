"""Unit tests for Phase 1 LLM Provider architecture and streaming."""

from unittest.mock import patch, MagicMock
import pytest
from offlinemind.llm.base import LLMProvider
from offlinemind.llm.ollama_provider import OllamaProvider
from offlinemind.llm.model_manager import ModelManager


class MockCustomProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "mock_custom"

    def is_available(self) -> bool:
        return True

    def list_models(self):
        return ["mock-model-v1"]

    def generate(self, prompt: str, system_prompt=None, temperature=0.7, **kwargs):
        return f"Mock reply to: {prompt}"

    def stream_generate(self, prompt: str, system_prompt=None, temperature=0.7, **kwargs):
        yield "Mock "
        yield "stream "
        yield "reply"


def test_provider_base_interface():
    provider = MockCustomProvider(model_name="mock-model-v1")
    assert provider.provider_name == "mock_custom"
    assert provider.is_available() is True
    assert provider.list_models() == ["mock-model-v1"]
    assert provider.generate("hello") == "Mock reply to: hello"
    tokens = list(provider.stream_generate("hello"))
    assert "".join(tokens) == "Mock stream reply"


@patch("requests.get")
@patch("requests.post")
def test_ollama_provider_generate_and_stream(mock_post, mock_get):
    # Mock tags
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"models": [{"name": "llama3.2:1b"}]}
    )
    # Mock non-streaming post
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"response": "Hello from Ollama!"},
        iter_lines=lambda: [
            b'{"response": "Hello ", "done": false}',
            b'{"response": "world!", "done": true}',
        ]
    )

    provider = OllamaProvider(model_name="llama3.2:1b", base_url="http://localhost:11434")
    with patch.object(provider, "_is_server_reachable", return_value=True):
        assert provider.is_available() is True
        assert provider.list_models() == ["llama3.2:1b"]

        reply = provider.generate("hi")
        assert reply == "Hello from Ollama!"

        stream_chunks = list(provider.stream_generate("hi"))
        assert "".join(stream_chunks) == "Hello world!"


def test_model_manager_status_and_switch():
    mm = ModelManager(default_model="llama3.2:1b")
    status = mm.get_status()
    assert "provider" in status
    assert "configured_model" in status
    assert status["configured_model"] == "llama3.2:1b"

    # Test dynamic model switch
    mm.switch_model("phi3:mini")
    assert mm.active_provider.model_name == "phi3:mini"
