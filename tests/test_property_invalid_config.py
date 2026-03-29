# Feature: alert-triage-agent, Property 10: Invalid configuration startup failure
# **Validates: Requirements 8.3, 9.2**

import os

import pytest
from hypothesis import given, settings, strategies as st

from config import load_config, SUPPORTED_LLM_PROVIDERS


# --- Env var helper ---

ENV_KEYS = (
    "LLM_PROVIDER", "LLM_MODEL", "RCA_AGENT_URL", "LLM_API_KEY",
    "SERVICE_PORT", "SYSTEM_PROMPT_URL", "SYSTEM_PROMPT_FILE",
)


def _clean_env():
    """Remove all config-related env vars."""
    for key in ENV_KEYS:
        os.environ.pop(key, None)


def _save_env():
    """Snapshot current config-related env vars."""
    return {k: os.environ.get(k) for k in ENV_KEYS}


def _restore_env(saved):
    """Restore env vars from a snapshot."""
    _clean_env()
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v


# --- Custom Hypothesis Strategies ---


def unsupported_provider():
    """Generate a provider string that is NOT in the supported set."""
    return st.text(
        alphabet=st.characters(blacklist_characters="\x00"),
        min_size=1,
        max_size=30,
    ).filter(
        lambda s: s.strip() and s not in SUPPORTED_LLM_PROVIDERS
    )


def empty_or_whitespace_model():
    """Generate empty or whitespace-only model names."""
    return st.one_of(
        st.just(""),
        st.text(
            alphabet=st.just(" "),
            min_size=1,
            max_size=20,
        ),
        st.text(
            alphabet=st.sampled_from([" ", "\t", "\n", "\r"]),
            min_size=1,
            max_size=10,
        ),
    )


def missing_rca_url():
    """Generate empty or whitespace-only RCA_AGENT_URL values."""
    return st.one_of(
        st.just(""),
        st.text(
            alphabet=st.sampled_from([" ", "\t", "\n", "\r"]),
            min_size=0,
            max_size=10,
        ),
    )


# --- Property Tests ---


@settings(max_examples=100)
@given(provider=unsupported_provider())
def test_unsupported_provider_fails_with_descriptive_error(provider):
    """Property 10: For any unsupported LLM provider, load_config() should
    raise ValueError with a descriptive error message."""

    saved = _save_env()
    try:
        _clean_env()
        os.environ["RCA_AGENT_URL"] = "http://rca-agent:8080"
        os.environ["LLM_PROVIDER"] = provider

        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            load_config()
    finally:
        _restore_env(saved)


@settings(max_examples=100)
@given(model=empty_or_whitespace_model())
def test_empty_model_name_fails_with_descriptive_error(model):
    """Property 10: For any empty or whitespace-only model name, load_config()
    should raise ValueError with a descriptive error message."""

    saved = _save_env()
    try:
        _clean_env()
        os.environ["RCA_AGENT_URL"] = "http://rca-agent:8080"
        os.environ["LLM_MODEL"] = model

        with pytest.raises(ValueError, match="LLM model name must not be empty"):
            load_config()
    finally:
        _restore_env(saved)


@settings(max_examples=100)
@given(rca_url=missing_rca_url())
def test_missing_rca_agent_url_uses_default(rca_url):
    """Property 10: For any missing or empty RCA_AGENT_URL, load_config()
    should use the default value 'http://localhost:9090'."""

    saved = _save_env()
    try:
        _clean_env()
        os.environ["RCA_AGENT_URL"] = rca_url

        cfg = load_config()
        assert cfg.rca_agent_url == "http://localhost:9090"
    finally:
        _restore_env(saved)
