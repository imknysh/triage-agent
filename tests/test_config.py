"""Unit tests for the configuration module."""

import os
import pytest
from config import AgentConfig, load_config, SUPPORTED_LLM_PROVIDERS


class TestAgentConfig:
    """Tests for the AgentConfig Pydantic model."""

    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.llm_provider == "openai"
        assert cfg.llm_model == "gpt-4o-mini"
        assert cfg.llm_api_key == ""
        assert cfg.rca_agent_url == "http://localhost:9090"
        assert cfg.service_port == 8080
        assert cfg.system_prompt_url is None
        assert cfg.system_prompt_file is None

    def test_custom_values(self):
        cfg = AgentConfig(
            llm_provider="anthropic",
            llm_model="claude-3",
            llm_api_key="sk-test",
            rca_agent_url="http://rca:9090",
            service_port=3000,
            system_prompt_url="http://prompts/sys.txt",
            system_prompt_file="/etc/config/prompt.txt",
        )
        assert cfg.llm_provider == "anthropic"
        assert cfg.llm_model == "claude-3"
        assert cfg.service_port == 3000

    def test_unsupported_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            AgentConfig(llm_provider="unsupported", rca_agent_url="http://rca:8080")

    def test_empty_model_raises(self):
        with pytest.raises(ValueError, match="LLM model name must not be empty"):
            AgentConfig(llm_model="", rca_agent_url="http://rca:8080")

    def test_whitespace_model_raises(self):
        with pytest.raises(ValueError, match="LLM model name must not be empty"):
            AgentConfig(llm_model="   ", rca_agent_url="http://rca:8080")

    def test_port_out_of_range(self):
        with pytest.raises(ValueError):
            AgentConfig(rca_agent_url="http://rca:8080", service_port=0)
        with pytest.raises(ValueError):
            AgentConfig(rca_agent_url="http://rca:8080", service_port=70000)

    def test_all_supported_providers(self):
        for provider in SUPPORTED_LLM_PROVIDERS:
            cfg = AgentConfig(llm_provider=provider, rca_agent_url="http://rca:8080")
            assert cfg.llm_provider == provider


class TestLoadConfig:
    """Tests for the load_config() function."""

    def test_missing_rca_url_uses_default(self, monkeypatch):
        monkeypatch.delenv("RCA_AGENT_URL", raising=False)
        for var in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "SERVICE_PORT",
                     "SYSTEM_PROMPT_URL", "SYSTEM_PROMPT_FILE"):
            monkeypatch.delenv(var, raising=False)
        cfg = load_config()
        assert cfg.rca_agent_url == "http://localhost:9090"

    def test_empty_rca_url_uses_default(self, monkeypatch):
        monkeypatch.setenv("RCA_AGENT_URL", "")
        for var in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "SERVICE_PORT",
                     "SYSTEM_PROMPT_URL", "SYSTEM_PROMPT_FILE"):
            monkeypatch.delenv(var, raising=False)
        cfg = load_config()
        assert cfg.rca_agent_url == "http://localhost:9090"

    def test_whitespace_rca_url_uses_default(self, monkeypatch):
        monkeypatch.setenv("RCA_AGENT_URL", "   ")
        for var in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "SERVICE_PORT",
                     "SYSTEM_PROMPT_URL", "SYSTEM_PROMPT_FILE"):
            monkeypatch.delenv(var, raising=False)
        cfg = load_config()
        assert cfg.rca_agent_url == "http://localhost:9090"

    def test_loads_defaults(self, monkeypatch):
        monkeypatch.setenv("RCA_AGENT_URL", "http://rca:8080")
        # Clear optional vars
        for var in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "SERVICE_PORT",
                     "SYSTEM_PROMPT_URL", "SYSTEM_PROMPT_FILE"):
            monkeypatch.delenv(var, raising=False)
        cfg = load_config()
        assert cfg.llm_provider == "openai"
        assert cfg.llm_model == "gpt-4o-mini"
        assert cfg.service_port == 8080

    def test_loads_custom_env(self, monkeypatch):
        monkeypatch.setenv("RCA_AGENT_URL", "http://rca:9090")
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("LLM_MODEL", "claude-3")
        monkeypatch.setenv("LLM_API_KEY", "sk-key")
        monkeypatch.setenv("SERVICE_PORT", "3000")
        monkeypatch.setenv("SYSTEM_PROMPT_URL", "http://prompts/sys.txt")
        monkeypatch.setenv("SYSTEM_PROMPT_FILE", "/etc/prompt.txt")
        cfg = load_config()
        assert cfg.llm_provider == "anthropic"
        assert cfg.llm_model == "claude-3"
        assert cfg.llm_api_key == "sk-key"
        assert cfg.rca_agent_url == "http://rca:9090"
        assert cfg.service_port == 3000
        assert cfg.system_prompt_url == "http://prompts/sys.txt"
        assert cfg.system_prompt_file == "/etc/prompt.txt"

    def test_invalid_provider_via_env_raises(self, monkeypatch):
        monkeypatch.setenv("RCA_AGENT_URL", "http://rca:8080")
        monkeypatch.setenv("LLM_PROVIDER", "invalid_provider")
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            load_config()
