"""Unit tests for the label_priority node."""

import json
from unittest.mock import MagicMock

import pytest

from nodes.label_priority import create_label_priority_node, _parse_priority


# ---------------------------------------------------------------------------
# _parse_priority helper tests
# ---------------------------------------------------------------------------

class TestParsePriority:
    def test_valid_p1(self):
        assert _parse_priority('{"priority": "P1", "event_type": "alert"}') == "P1"

    def test_valid_p2(self):
        assert _parse_priority('{"priority": "P2"}') == "P2"

    def test_valid_p3(self):
        assert _parse_priority('{"priority": "P3", "event_type": "notification"}') == "P3"

    def test_case_insensitive(self):
        assert _parse_priority('{"priority": "p1"}') == "P1"

    def test_whitespace_trimmed(self):
        assert _parse_priority('{"priority": " P2 "}') == "P2"

    def test_invalid_value(self):
        assert _parse_priority('{"priority": "P4"}') is None

    def test_missing_field(self):
        assert _parse_priority('{"event_type": "alert"}') is None

    def test_invalid_json(self):
        assert _parse_priority("not json at all") is None

    def test_empty_string(self):
        assert _parse_priority('{"priority": ""}') is None


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


class TestLabelPriorityNode:
    SYSTEM_PROMPT = "You are a triage assistant."

    def test_returns_p1_on_first_try(self):
        llm = _make_llm_mock(['{"priority": "P1", "event_type": "alert"}'])
        node = create_label_priority_node(llm, self.SYSTEM_PROMPT)

        result = node({"raw_message": {"AlarmName": "HighCPU"}})

        assert result == {"labels": {"priority": "P1"}}
        assert llm.invoke.call_count == 1

    def test_returns_p2_on_first_try(self):
        llm = _make_llm_mock(['{"priority": "P2"}'])
        node = create_label_priority_node(llm, self.SYSTEM_PROMPT)

        result = node({"raw_message": {"warning": "high latency"}})

        assert result == {"labels": {"priority": "P2"}}

    def test_returns_p3_on_first_try(self):
        llm = _make_llm_mock(['{"priority": "P3"}'])
        node = create_label_priority_node(llm, self.SYSTEM_PROMPT)

        result = node({"raw_message": {"info": "deployment complete"}})

        assert result == {"labels": {"priority": "P3"}}

    def test_retries_once_on_invalid_then_succeeds(self):
        llm = _make_llm_mock([
            '{"priority": "critical"}',  # invalid first attempt
            '{"priority": "P1"}',        # valid retry
        ])
        node = create_label_priority_node(llm, self.SYSTEM_PROMPT)

        result = node({"raw_message": {"AlarmName": "DiskFull"}})

        assert result == {"labels": {"priority": "P1"}}
        assert llm.invoke.call_count == 2

    def test_raises_after_two_invalid_attempts(self):
        llm = _make_llm_mock([
            "garbage output",
            '{"priority": "HIGH"}',
        ])
        node = create_label_priority_node(llm, self.SYSTEM_PROMPT)

        with pytest.raises(ValueError, match="invalid priority after 2 attempts"):
            node({"raw_message": {"foo": "bar"}})

        assert llm.invoke.call_count == 2

    def test_system_prompt_passed_to_llm(self):
        llm = _make_llm_mock(['{"priority": "P2"}'])
        node = create_label_priority_node(llm, self.SYSTEM_PROMPT)

        node({"raw_message": {"msg": "hello"}})

        call_args = llm.invoke.call_args[0][0]
        assert call_args[0]["role"] == "system"
        assert call_args[0]["content"] == self.SYSTEM_PROMPT

    def test_raw_message_serialised_as_user_content(self):
        llm = _make_llm_mock(['{"priority": "P1"}'])
        node = create_label_priority_node(llm, self.SYSTEM_PROMPT)
        msg = {"AlarmName": "HighCPU", "NewStateValue": "ALARM"}

        node({"raw_message": msg})

        call_args = llm.invoke.call_args[0][0]
        assert call_args[1]["role"] == "user"
        assert json.loads(call_args[1]["content"]) == msg

    def test_empty_raw_message(self):
        llm = _make_llm_mock(['{"priority": "P3"}'])
        node = create_label_priority_node(llm, self.SYSTEM_PROMPT)

        result = node({"raw_message": {}})

        assert result == {"labels": {"priority": "P3"}}
