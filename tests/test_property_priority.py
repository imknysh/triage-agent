# Feature: alert-triage-agent, Property 5: Priority label validity
# **Validates: Requirements 4.1**

import json
from unittest.mock import MagicMock

from hypothesis import given, settings, strategies as st

from nodes.label_priority import create_label_priority_node


# --- Reusable strategies ---

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

_VALID_PRIORITIES = ("P1", "P2", "P3")


def _make_mock_llm(priority: str):
    """Return a mock LLM that responds with valid JSON containing the given priority."""
    mock = MagicMock()
    resp = MagicMock()
    resp.content = json.dumps({"priority": priority, "event_type": "alert"})
    mock.invoke.return_value = resp
    return mock


# --- Property Test ---

SYSTEM_PROMPT = "You are a triage assistant."


@settings(max_examples=150)
@given(
    raw_message=alert_message(),
    priority=st.sampled_from(_VALID_PRIORITIES),
)
def test_priority_label_is_p1_p2_or_p3(raw_message, priority):
    """Property 5: For any valid alert message that passes through the priority
    labeling node, the resulting priority label must be exactly one of
    'P1', 'P2', or 'P3'."""

    llm = _make_mock_llm(priority)
    node = create_label_priority_node(llm, SYSTEM_PROMPT)

    state = {"raw_message": raw_message}
    result = node(state)

    # The node must return a labels dict with a priority key
    assert "labels" in result, "Node result missing 'labels'"
    assert "priority" in result["labels"], "Labels missing 'priority'"

    returned_priority = result["labels"]["priority"]
    assert returned_priority in {"P1", "P2", "P3"}, (
        f"priority must be 'P1', 'P2', or 'P3', got {returned_priority!r}"
    )
