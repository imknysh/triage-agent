"""Unit tests for the A2A forwarder module."""

import json
import logging
from unittest.mock import patch, MagicMock

import httpx
import pytest

from forwarder import build_a2a_message, forward_to_rca, MAX_RETRIES


# ── build_a2a_message ───────────────────────────────────────────────────────

class TestBuildA2AMessage:
    def test_envelope_structure(self):
        msg = {"original_message": {"foo": 1}, "labels": {"source": "CW"}}
        envelope = build_a2a_message(msg)

        assert envelope["jsonrpc"] == "2.0"
        assert envelope["method"] == "message/send"
        assert "id" in envelope
        assert isinstance(envelope["id"], str)
        assert "params" in envelope

    def test_message_part_contains_enriched_data(self):
        msg = {"labels": {"priority": "P1"}}
        envelope = build_a2a_message(msg)

        message = envelope["params"]["message"]
        assert message["role"] == "user"
        assert "messageId" in message
        assert len(message["parts"]) == 1
        part = message["parts"][0]
        assert part["kind"] == "text"
        assert json.loads(part["text"]) == msg

    def test_unique_request_ids(self):
        msg = {"x": 1}
        ids = {build_a2a_message(msg)["id"] for _ in range(50)}
        assert len(ids) == 50, "Request IDs should be unique"

    def test_unique_message_ids(self):
        msg = {"x": 1}
        ids = {build_a2a_message(msg)["params"]["message"]["messageId"] for _ in range(50)}
        assert len(ids) == 50, "Message IDs should be unique"


# ── forward_to_rca ─────────────────────────────────────────────────────────

class TestForwardToRca:
    @patch("forwarder.httpx.post")
    def test_success_on_first_attempt(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        result = forward_to_rca({"a": 1}, "http://rca:8080")

        assert result is True
        assert mock_post.call_count == 1
        args, _ = mock_post.call_args
        assert args[0] == "http://rca:8080"

    @patch("forwarder.time.sleep")
    @patch("forwarder.httpx.post")
    def test_retries_on_http_error(self, mock_post, mock_sleep):
        mock_post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock(status_code=500)
        )
        result = forward_to_rca({"a": 1}, "http://rca:8080")

        assert result is False
        assert mock_post.call_count == MAX_RETRIES

    @patch("forwarder.time.sleep")
    @patch("forwarder.httpx.post")
    def test_retries_on_connection_error(self, mock_post, mock_sleep):
        mock_post.side_effect = httpx.ConnectError("refused")
        result = forward_to_rca({"a": 1}, "http://rca:8080")

        assert result is False
        assert mock_post.call_count == MAX_RETRIES

    @patch("forwarder.time.sleep")
    @patch("forwarder.httpx.post")
    def test_success_after_retries(self, mock_post, mock_sleep):
        fail = httpx.ConnectError("refused")
        ok = MagicMock(status_code=200, raise_for_status=MagicMock())
        mock_post.side_effect = [fail, fail, ok]

        result = forward_to_rca({"a": 1}, "http://rca:8080")
        assert result is True
        assert mock_post.call_count == 3

    @patch("forwarder.time.sleep")
    @patch("forwarder.httpx.post")
    def test_exponential_backoff_delays(self, mock_post, mock_sleep):
        mock_post.side_effect = httpx.ConnectError("refused")
        forward_to_rca({"a": 1}, "http://rca:8080")

        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    @patch("forwarder.time.sleep")
    @patch("forwarder.httpx.post")
    def test_logs_each_failure(self, mock_post, mock_sleep, caplog):
        mock_post.side_effect = httpx.ConnectError("refused")
        with caplog.at_level(logging.ERROR, logger="forwarder"):
            forward_to_rca({"a": 1}, "http://rca:8080")

        error_logs = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_logs) == MAX_RETRIES + 1

    @patch("forwarder.time.sleep")
    @patch("forwarder.httpx.post")
    def test_logs_full_message_on_final_failure(self, mock_post, mock_sleep, caplog):
        mock_post.side_effect = httpx.ConnectError("refused")
        msg = {"original_message": {"key": "value"}, "labels": {"source": "CW"}}
        with caplog.at_level(logging.ERROR, logger="forwarder"):
            forward_to_rca(msg, "http://rca:8080")

        final_log = caplog.records[-1].message
        assert "Enriched message" in final_log
        assert "CW" in final_log

    @patch("forwarder.httpx.post")
    def test_trailing_slash_in_url(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        forward_to_rca({"a": 1}, "http://rca:8080/")

        args, _ = mock_post.call_args
        assert args[0] == "http://rca:8080"
