# Feature: alert-triage-agent, Property 4: Event type label validity
# **Validates: Requirements 3.1**

import json
from unittest.mock import MagicMock

from hypothesis import given, settings, strategies as st

from nodes.label_event_type import create_label_event_type_node


# --- Reusable strategies (same as test_property_enriched_message.py) ---

def cloudwatch_message():
    """Generate realistic CloudWatch alarm messages."""
    return st.fixed_dictionaries({
        "AlarmName": st.text(min_size=1, max_size=50),
        "NewStateValue": st.sampled_from(["ALARM", "OK", "INSUFFICIENT_DATA"]),
        "NewStateReason": st.text(min_size=1, max_size=100),
        "StateChangeTime": st.text(min_size=1, max_size=30),
    })


def sns_message():
    """Generate realistic SNS notification messages."""
    return st.fixed_dictionaries({
        "Type": st.just("Notification"),
        "TopicArn": st.from_regex(
            r"arn:aws:sns:us-east-1:[0-9]{12}:[a-zA-Z0-9_-]+", fullmatch=True
        ),
        "Subject": st.text(min_size=1, max_size=80),
        "Message": st.text(min_size=1, max_size=200),
    })


def eventbridge_message():
    """Generate realistic EventBridge messages."""
    return st.fixed_dictionaries({
        "source": st.from_regex(r"aws\.[a-z]+", fullmatch=True),
        "detail-type": st.text(min_size=1, max_size=60),
        "detail": st.fixed_dictionaries({
            "status": st.text(min_size=1, max_size=20),
        }),
        "account": st.from_regex(r"[0-9]{12}", fullmatch=True),
        "region": st.sampled_from(["us-east-1", "us-west-2", "eu-west-1"]),
    })


def unknown_message():
    """Generate valid JSON dicts that don't match any known source pattern."""
    return st.fixed_dictionaries({
        "id": st.text(min_size=1, max_size=30),
        "data": st.text(min_size=1, max_size=100),
        "timestamp": st.text(min_size=1, max_size=30),
    })


def alert_message():
    """Composite strategy drawing from all source types."""
    return st.one_of(
        cloudwatch_message(),
        sns_message(),
        eventbridge_message(),
        unknown_message(),
    )


# --- LLM mock helper ---

_VALID_EVENT_TYPES = ("alert", "notification")


def _make_mock_llm(event_type: str):
    """Return a mock LLM that responds with a valid JSON containing the given event_type."""
    mock = MagicMock()
    resp = MagicMock()
    resp.content = json.dumps({"event_type": event_type, "priority": "P1"})
    mock.invoke.return_value = resp
    return mock


# --- Property Test ---

SYSTEM_PROMPT = "You are a triage assistant."


@settings(max_examples=150)
@given(
    raw_message=alert_message(),
    event_type=st.sampled_from(_VALID_EVENT_TYPES),
)
def test_event_type_label_is_alert_or_notification(raw_message, event_type):
    """Property 4: For any valid alert message that passes through the event
    type labeling node, the resulting event_type label must be exactly one of
    'alert' or 'notification'."""

    llm = _make_mock_llm(event_type)
    node = create_label_event_type_node(llm, SYSTEM_PROMPT)

    state = {"raw_message": raw_message}
    result = node(state)

    # The node must return a labels dict with an event_type key
    assert "labels" in result, "Node result missing 'labels'"
    assert "event_type" in result["labels"], "Labels missing 'event_type'"

    returned_event_type = result["labels"]["event_type"]
    assert returned_event_type in {"alert", "notification"}, (
        f"event_type must be 'alert' or 'notification', got {returned_event_type!r}"
    )
