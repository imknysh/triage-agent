# Feature: alert-triage-agent, Property 11: System prompt fallback chain priority
# **Validates: Requirements 7.2, 7.3, 7.4, 7.5, 7.6, 7.7**

import os
from unittest.mock import patch, MagicMock

import httpx
from hypothesis import given, settings, strategies as st, assume

from prompt_loader import load_system_prompt


# --- Source availability states ---
# Each prompt source can be: "available", "failing", or "not_configured"
# Exception: default can only be "available" or "failing" (always attempted)

SOURCE_STATES = ["available", "failing", "not_configured"]
DEFAULT_STATES = ["available", "failing"]


# --- Strategies ---

def prompt_source_config():
    """Generate random combinations of prompt source availability.

    Returns a tuple of (url_state, file_state, default_state, url_content, file_content, default_content)
    where each state is one of 'available', 'failing', or 'not_configured',
    and content strings are the prompt text returned when available.
    """
    return st.tuples(
        st.sampled_from(SOURCE_STATES),       # url_state
        st.sampled_from(SOURCE_STATES),       # file_state
        st.sampled_from(DEFAULT_STATES),      # default_state
        st.text(min_size=1, max_size=200),    # url_content
        st.text(min_size=1, max_size=200),    # file_content
        st.text(min_size=1, max_size=200),    # default_content
    )


# --- Env var helper ---

ENV_KEYS = ("SYSTEM_PROMPT_URL", "SYSTEM_PROMPT_FILE")


def _clean_env():
    for key in ENV_KEYS:
        os.environ.pop(key, None)


# --- Property Test ---

@settings(max_examples=150)
@given(config=prompt_source_config())
def test_prompt_fallback_chain_priority(config):
    """Property 11: For any combination of prompt source configurations where
    at least one source is available, the prompt loader should return the content
    from the highest-priority available source (URL > file > default)."""

    url_state, file_state, default_state, url_content, file_content, default_content = config

    # At least one source must be available
    assume(
        url_state == "available"
        or file_state == "available"
        or default_state == "available"
    )

    saved = {k: os.environ.get(k) for k in ENV_KEYS}

    try:
        _clean_env()

        # --- Configure URL source ---
        if url_state == "not_configured":
            # No env var set
            pass
        else:
            os.environ["SYSTEM_PROMPT_URL"] = "https://example.com/prompt.txt"

        # --- Configure file source ---
        if file_state == "not_configured":
            pass
        else:
            os.environ["SYSTEM_PROMPT_FILE"] = "/tmp/test_prompt.txt"

        # --- Determine expected result based on priority ---
        if url_state == "available":
            expected = url_content
        elif file_state == "available":
            expected = file_content
        elif default_state == "available":
            expected = default_content
        else:
            # Should not reach here due to assume() above
            return

        # --- Build mocks ---
        def mock_httpx_get(url, **kwargs):
            if url_state == "available":
                resp = MagicMock()
                resp.text = url_content
                resp.raise_for_status = MagicMock()
                return resp
            elif url_state == "failing":
                raise httpx.ConnectError("simulated URL failure")
            # not_configured: won't be called

        def mock_read_text(self):
            path_str = str(self)
            if path_str == "/tmp/test_prompt.txt":
                if file_state == "available":
                    return file_content
                elif file_state == "failing":
                    raise FileNotFoundError("simulated file failure")
            # Default file path
            if "prompts/system_prompt.txt" in path_str or path_str == "prompts/system_prompt.txt":
                if default_state == "available":
                    return default_content
                else:
                    raise FileNotFoundError("simulated default file failure")
            raise FileNotFoundError(f"unexpected path: {path_str}")

        with patch("prompt_loader.httpx.get", side_effect=mock_httpx_get):
            with patch("prompt_loader.Path.read_text", mock_read_text):
                result = load_system_prompt()

        assert result == expected, (
            f"Expected content from highest-priority source, got mismatch.\n"
            f"  url_state={url_state}, file_state={file_state}, default_state={default_state}\n"
            f"  expected={expected!r}, got={result!r}"
        )

    finally:
        _clean_env()
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
