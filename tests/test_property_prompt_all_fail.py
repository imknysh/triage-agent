# Feature: alert-triage-agent, Property 12: All prompt sources failure
# **Validates: Requirements 7.8**

import os
from unittest.mock import patch, MagicMock

import httpx
import pytest
from hypothesis import given, settings, strategies as st

from prompt_loader import load_system_prompt, PromptLoadError


# --- Strategies ---

# Generate non-empty failure reason strings for each prompt source
failure_reasons = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="\x00"),
    min_size=1,
    max_size=150,
)


# --- Property Test ---

@settings(max_examples=150)
@given(
    url_reason=failure_reasons,
    file_reason=failure_reasons,
    default_reason=failure_reasons,
)
def test_all_prompt_sources_failure(url_reason, file_reason, default_reason):
    """Property 12: For any configuration where all prompt sources fail,
    the agent should fail to start and produce an error message listing
    each attempted source and its specific failure reason."""

    saved = {
        "SYSTEM_PROMPT_URL": os.environ.get("SYSTEM_PROMPT_URL"),
        "SYSTEM_PROMPT_FILE": os.environ.get("SYSTEM_PROMPT_FILE"),
    }

    try:
        # Configure all three sources so all are attempted
        os.environ["SYSTEM_PROMPT_URL"] = "https://example.com/prompt.txt"
        os.environ["SYSTEM_PROMPT_FILE"] = "/tmp/nonexistent_prompt.txt"

        # Mock URL fetch to fail with the generated reason
        def mock_httpx_get(url, **kwargs):
            raise httpx.ConnectError(url_reason)

        # Mock file reads to fail with the generated reasons
        def mock_read_text(self):
            path_str = str(self)
            if path_str == "/tmp/nonexistent_prompt.txt":
                raise FileNotFoundError(file_reason)
            if "prompts/system_prompt.txt" in path_str or path_str == "prompts/system_prompt.txt":
                raise FileNotFoundError(default_reason)
            raise FileNotFoundError(f"unexpected path: {path_str}")

        with patch("prompt_loader.httpx.get", side_effect=mock_httpx_get):
            with patch("prompt_loader.Path.read_text", mock_read_text):
                with pytest.raises(PromptLoadError) as exc_info:
                    load_system_prompt()

        error_msg = str(exc_info.value)

        # Verify the error message mentions all three sources
        assert "HTTP URL" in error_msg, (
            f"Error message should mention HTTP URL source.\n  Got: {error_msg}"
        )
        assert "File path" in error_msg, (
            f"Error message should mention File path source.\n  Got: {error_msg}"
        )
        assert "Default file" in error_msg, (
            f"Error message should mention Default file source.\n  Got: {error_msg}"
        )

        # Verify each failure reason appears in the error message
        assert url_reason in error_msg, (
            f"Error message should contain URL failure reason '{url_reason}'.\n  Got: {error_msg}"
        )
        assert file_reason in error_msg, (
            f"Error message should contain file failure reason '{file_reason}'.\n  Got: {error_msg}"
        )
        assert default_reason in error_msg, (
            f"Error message should contain default failure reason '{default_reason}'.\n  Got: {error_msg}"
        )

    finally:
        # Restore original env vars
        for key in ("SYSTEM_PROMPT_URL", "SYSTEM_PROMPT_FILE"):
            os.environ.pop(key, None)
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
