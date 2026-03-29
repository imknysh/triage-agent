# Feature: alert-triage-agent, Property 9: Configuration application
# **Validates: Requirements 8.1**

import os

from hypothesis import given, settings, strategies as st

from config import AgentConfig, load_config, SUPPORTED_LLM_PROVIDERS


# --- Custom Hypothesis Strategies ---

PROVIDERS = sorted(SUPPORTED_LLM_PROVIDERS)  # ["anthropic", "azure", "openai"]


def valid_provider():
    """Generate a supported LLM provider."""
    return st.sampled_from(PROVIDERS)


def valid_model_name():
    """Generate a non-empty model name string."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Pd"), whitelist_characters=".-_/"),
        min_size=1,
        max_size=60,
    )


def valid_provider_model_pair():
    """Generate a valid (provider, model) combination."""
    return st.tuples(valid_provider(), valid_model_name())


# --- Env var helper ---

ENV_KEYS = ("LLM_PROVIDER", "LLM_MODEL", "RCA_AGENT_URL", "LLM_API_KEY",
            "SERVICE_PORT", "SYSTEM_PROMPT_URL", "SYSTEM_PROMPT_FILE")


def _clean_env():
    """Remove all config-related env vars."""
    for key in ENV_KEYS:
        os.environ.pop(key, None)


# --- Property Test ---


@settings(max_examples=150)
@given(pair=valid_provider_model_pair())
def test_config_applies_provider_and_model(pair):
    """Property 9: For any valid combination of LLM_PROVIDER and LLM_MODEL
    environment variables, the agent should initialize with those values
    reflected in its configuration."""

    provider, model = pair
    saved = {k: os.environ.get(k) for k in ENV_KEYS}

    try:
        _clean_env()
        os.environ["LLM_PROVIDER"] = provider
        os.environ["LLM_MODEL"] = model
        os.environ["RCA_AGENT_URL"] = "http://rca-agent:8080"

        cfg = load_config()

        assert isinstance(cfg, AgentConfig)
        assert cfg.llm_provider == provider, (
            f"Expected provider '{provider}', got '{cfg.llm_provider}'"
        )
        assert cfg.llm_model == model, (
            f"Expected model '{model}', got '{cfg.llm_model}'"
        )
    finally:
        # Restore original env state
        _clean_env()
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
