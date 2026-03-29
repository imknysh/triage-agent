"""Unit tests for the label_event_type node."""

import json
from unittest.mock import MagicMock

import pytest

from nodes.label_event_type import create_label_event_type_node, _parse_event_type


# ---------------------------------------------------------------------------
# _parse_event_type helper tests
# ---------------------------------------------------------------------------

class TestParseEventType:
    def test_valid_alert(self):
        assert _parse_event_type('{"event_type": "alert", "priority": "P1"}') == "alert"

    def test_valid_notification(self):
        assert _parse_event_type('{"event_type": "notification", "priority": "P3"}') == "notification"

    def test_case_insensitive(self):
        assert _parse_event_type('{"event_type": "ALERT"}') == "alert"

    def test_whitespace_trimmed(self):
        assert _parse_event_type('{"event_type": " notification "}') == "notification"

    def test_invalid_value(self):
        assert _parse_event_type('{"event_type": "warning"}') is None

    def test_missing_field(self):
        assert _parse_event_type('{"priority": "P1"}') is None

    def test_invalid_json(self):
        assert _parse_event_type("not json at all") is None

    def test_empty_string(self):
        assert _parse_event_type('{"event_type": ""}') is None


# ---------------------------------------------------------------------------
# Factory / node function tests
# ---------------------------------------------------------------------------

def _make_llm_mock(responses: list[str]):
    """Create a mock LLM that returns the given response strings in order."""
    mock = MagicMock()
    side_effects = []
    for text in responses:
        resp = MagicMock()
        resp.content = text
        side_effects.append(resp)
    mock.invoke.side_effect = side_effects
    return mock


class TestLabelEventTypeNode:
    SYSTEM_PROMPT = "You are a triage assistant."

    def test_returns_alert_on_first_try(self):
        llm = _make_llm_mock(['{"event_type": "alert", "priority": "P1"}'])
        node = create_label_event_type_node(llm, self.SYSTEM_PROMPT)

        result = node({"raw_message": {"AlarmName": "HighCPU"}})

        assert result == {"labels": {"event_type": "alert"}}
        assert llm.invoke.call_count == 1

    def test_returns_notification_on_first_try(self):
        llm = _make_llm_mock(['{"event_type": "notification", "priority": "P3"}'])
        node = create_label_event_type_node(llm, self.SYSTEM_PROMPT)

        result = node({"raw_message": {"info": "deployment complete"}})

        assert result == {"labels": {"event_type": "notification"}}

    def test_retries_once_on_invalid_then_succeeds(self):
        llm = _make_llm_mock([
            '{"event_type": "unknown"}',  # invalid first attempt
            '{"event_type": "alert", "priority": "P2"}',  # valid retry
        ])
        node = create_label_event_type_node(llm, self.SYSTEM_PROMPT)

        result = node({"raw_message": {"AlarmName": "DiskFull"}})

        assert result == {"labels": {"event_type": "alert"}}
        assert llm.invoke.call_count == 2

    def test_raises_after_two_invalid_attempts(self):
        llm = _make_llm_mock([
            "garbage output",
            '{"event_type": "bad"}',
        ])
        node = create_label_event_type_node(llm, self.SYSTEM_PROMPT)

        with pytest.raises(ValueError, match="invalid event_type after 2 attempts"):
            node({"raw_message": {"foo": "bar"}})

        assert llm.invoke.call_count == 2

    def test_system_prompt_passed_to_llm(self):
        llm = _make_llm_mock(['{"event_type": "notification"}'])
        node = create_label_event_type_node(llm, self.SYSTEM_PROMPT)

        node({"raw_message": {"msg": "hello"}})

        call_args = llm.invoke.call_args[0][0]
        assert call_args[0]["role"] == "system"
        assert call_args[0]["content"] == self.SYSTEM_PROMPT

    def test_raw_message_serialised_as_user_content(self):
        llm = _make_llm_mock(['{"event_type": "alert"}'])
        node = create_label_event_type_node(llm, self.SYSTEM_PROMPT)
        msg = {"AlarmName": "HighCPU", "NewStateValue": "ALARM"}

        node({"raw_message": msg})

        call_args = llm.invoke.call_args[0][0]
        assert call_args[1]["role"] == "user"
        assert json.loads(call_args[1]["content"]) == msg

    def test_empty_raw_message(self):
        llm = _make_llm_mock(['{"event_type": "notification"}'])
        node = create_label_event_type_node(llm, self.SYSTEM_PROMPT)

        result = node({"raw_message": {}})

        assert result == {"labels": {"event_type": "notification"}}
