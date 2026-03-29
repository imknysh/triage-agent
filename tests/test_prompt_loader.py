"""Unit tests for the system prompt loader."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx
import pytest

from prompt_loader import load_system_prompt, PromptLoadError


class TestLoadFromURL:
    """Tests for loading system prompt from HTTP URL."""

    def test_loads_from_url_when_set(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SYSTEM_PROMPT_URL", raising=False)
        monkeypatch.delenv("SYSTEM_PROMPT_FILE", raising=False)
        monkeypatch.setenv("SYSTEM_PROMPT_URL", "https://example.com/prompt.txt")

        mock_resp = MagicMock()
        mock_resp.text = "prompt from url"
        mock_resp.raise_for_status = MagicMock()

        with patch("prompt_loader.httpx.get", return_value=mock_resp) as mock_get:
            result = load_system_prompt()

        assert result == "prompt from url"
        mock_get.assert_called_once_with("https://example.com/prompt.txt", timeout=10)

    def test_falls_through_on_url_failure(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SYSTEM_PROMPT_URL", "https://example.com/bad")
        monkeypatch.delenv("SYSTEM_PROMPT_FILE", raising=False)

        with patch("prompt_loader.httpx.get", side_effect=httpx.ConnectError("fail")):
            # Should fall through to default file
            result = load_system_prompt()

        assert len(result) > 0  # Got the default prompt


class TestLoadFromFile:
    """Tests for loading system prompt from file path."""

    def test_loads_from_file_when_set(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SYSTEM_PROMPT_URL", raising=False)
        prompt_file = tmp_path / "custom_prompt.txt"
        prompt_file.write_text("prompt from file")
        monkeypatch.setenv("SYSTEM_PROMPT_FILE", str(prompt_file))

        result = load_system_prompt()
        assert result == "prompt from file"

    def test_falls_through_on_file_not_found(self, monkeypatch):
        monkeypatch.delenv("SYSTEM_PROMPT_URL", raising=False)
        monkeypatch.setenv("SYSTEM_PROMPT_FILE", "/nonexistent/path/prompt.txt")

        # Should fall through to default file
        result = load_system_prompt()
        assert len(result) > 0


class TestLoadFromDefault:
    """Tests for loading system prompt from default file."""

    def test_loads_default_when_no_env_vars(self, monkeypatch):
        monkeypatch.delenv("SYSTEM_PROMPT_URL", raising=False)
        monkeypatch.delenv("SYSTEM_PROMPT_FILE", raising=False)

        result = load_system_prompt()
        assert "alert triage" in result.lower()


class TestAllSourcesFail:
    """Tests for PromptLoadError when all sources fail."""

    def test_raises_prompt_load_error_when_all_fail(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SYSTEM_PROMPT_URL", "https://example.com/bad")
        monkeypatch.setenv("SYSTEM_PROMPT_FILE", "/nonexistent/file.txt")

        with patch("prompt_loader.httpx.get", side_effect=httpx.ConnectError("conn err")):
            with patch("prompt_loader.Path.read_text", side_effect=FileNotFoundError("not found")):
                with pytest.raises(PromptLoadError) as exc_info:
                    load_system_prompt()

        error_msg = str(exc_info.value)
        assert "Failed to load system prompt from all sources" in error_msg
        assert "HTTP URL" in error_msg
        assert "File path" in error_msg
        assert "Default file" in error_msg

    def test_error_lists_only_attempted_sources(self, monkeypatch):
        """When no URL/file env vars set, only default file error is listed."""
        monkeypatch.delenv("SYSTEM_PROMPT_URL", raising=False)
        monkeypatch.delenv("SYSTEM_PROMPT_FILE", raising=False)

        with patch("prompt_loader.Path.read_text", side_effect=FileNotFoundError("missing")):
            with pytest.raises(PromptLoadError) as exc_info:
                load_system_prompt()

        error_msg = str(exc_info.value)
        assert "Default file" in error_msg
        assert "HTTP URL" not in error_msg
        assert "File path" not in error_msg


class TestPriorityOrder:
    """Tests for fallback chain priority order."""

    def test_url_takes_priority_over_file(self, monkeypatch, tmp_path):
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("from file")
        monkeypatch.setenv("SYSTEM_PROMPT_URL", "https://example.com/prompt")
        monkeypatch.setenv("SYSTEM_PROMPT_FILE", str(prompt_file))

        mock_resp = MagicMock()
        mock_resp.text = "from url"
        mock_resp.raise_for_status = MagicMock()

        with patch("prompt_loader.httpx.get", return_value=mock_resp):
            result = load_system_prompt()

        assert result == "from url"

    def test_file_takes_priority_over_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SYSTEM_PROMPT_URL", raising=False)
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("from custom file")
        monkeypatch.setenv("SYSTEM_PROMPT_FILE", str(prompt_file))

        result = load_system_prompt()
        assert result == "from custom file"
