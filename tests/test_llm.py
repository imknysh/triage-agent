"""Unit tests for the LLM client module."""

import pytest
from unittest.mock import patch

from config import AgentConfig
from llm import create_llm_client


def _make_config(**overrides) -> AgentConfig:
    defaults = {
        "rca_agent_url": "http://rca.example.com",
        "llm_provider": "openai",
        "llm_model": "gpt-4o-mini",
        "llm_api_key": "test-key",
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)


class TestCreateLlmClient:
    """Tests for create_llm_client function."""

    def test_openai_provider_returns_chat_openai(self):
        config = _make_config(llm_provider="openai")
        client = create_llm_client(config)
        assert client.model_name == "gpt-4o-mini"

    def test_azure_provider_returns_client(self):
        config = _make_config(llm_provider="azure")
        client = create_llm_client(config)
        assert client.model_name == "gpt-4o-mini"

    def test_anthropic_provider_returns_client(self):
        config = _make_config(llm_provider="anthropic")
        client = create_llm_client(config)
        assert client.model_name == "gpt-4o-mini"

    def test_custom_model_name_is_passed(self):
        config = _make_config(llm_model="gpt-3.5-turbo")
        client = create_llm_client(config)
        assert client.model_name == "gpt-3.5-turbo"

    def test_api_key_is_passed(self):
        config = _make_config(llm_api_key="sk-my-secret-key")
        client = create_llm_client(config)
        assert client.openai_api_key.get_secret_value() == "sk-my-secret-key"

    def test_unsupported_provider_raises_value_error(self):
        # Build config bypassing pydantic validation for provider
        config = _make_config(llm_provider="openai")
        # Manually override to simulate an unsupported provider reaching create_llm_client
        object.__setattr__(config, "llm_provider", "unsupported")
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm_client(config)

    def test_empty_model_raises_value_error(self):
        config = _make_config(llm_provider="openai")
        object.__setattr__(config, "llm_model", "")
        with pytest.raises(ValueError, match="LLM model name must not be empty"):
            create_llm_client(config)

    def test_whitespace_model_raises_value_error(self):
        config = _make_config(llm_provider="openai")
        object.__setattr__(config, "llm_model", "   ")
        with pytest.raises(ValueError, match="LLM model name must not be empty"):
            create_llm_client(config)

    def test_error_message_lists_supported_providers(self):
        config = _make_config(llm_provider="openai")
        object.__setattr__(config, "llm_provider", "gemini")
        with pytest.raises(ValueError, match="anthropic.*azure.*openai"):
            create_llm_client(config)
