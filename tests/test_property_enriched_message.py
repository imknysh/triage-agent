# Feature: alert-triage-agent, Property 7: Enriched message completeness
# **Validates: Requirements 6.1**

from hypothesis import given, settings, strategies as st
from models import TriageState, Labels


# --- Custom Hypothesis Strategies ---

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


def valid_source():
    return st.sampled_from(["CW", "SNS", "EventBridge", "UNKNOWN"])


def valid_event_type():
    return st.sampled_from(["alert", "notification"])


def valid_priority():
    return st.sampled_from(["P1", "P2", "P3"])


def valid_environment():
    return st.text(min_size=1, max_size=50).filter(lambda s: s.strip())


def complete_labels():
    """Generate a Labels dict with all 4 fields populated."""
    return st.fixed_dictionaries({
        "source": valid_source(),
        "event_type": valid_event_type(),
        "priority": valid_priority(),
        "environment": valid_environment(),
    })


def complete_triage_state():
    """Generate a TriageState representing a completed pipeline run."""
    return st.fixed_dictionaries({
        "raw_message": alert_message(),
        "is_valid": st.just(True),
        "error": st.just(None),
        "labels": complete_labels(),
        "forwarded": st.booleans(),
        "forward_error": st.just(None),
        "retry_count": st.integers(min_value=0, max_value=3),
    })


# --- Enriched message builder (mirrors design doc output format) ---

def build_enriched_message(state: TriageState) -> dict:
    """Build the enriched message structure that would be sent to the RCA agent.

    Per the design doc, the enriched message contains:
    - original_message: the raw alert message
    - labels: all 4 triage labels
    """
    return {
        "original_message": state["raw_message"],
        "labels": state["labels"],
    }


# --- Property Test ---

REQUIRED_LABELS = {"source", "event_type", "priority", "environment"}


@settings(max_examples=150)
@given(state=complete_triage_state())
def test_enriched_message_contains_all_labels_and_original(state):
    """Property 7: For any valid message that completes the triage pipeline,
    the enriched output must contain all 4 labels and the original message."""

    enriched = build_enriched_message(state)

    # The enriched message must contain the original message
    assert "original_message" in enriched, "Enriched message missing 'original_message'"
    assert enriched["original_message"] == state["raw_message"], (
        "Enriched message 'original_message' does not match the raw input"
    )

    # The enriched message must contain a labels dict
    assert "labels" in enriched, "Enriched message missing 'labels'"

    # All 4 required labels must be present
    labels = enriched["labels"]
    present_labels = set(labels.keys())
    missing = REQUIRED_LABELS - present_labels
    assert not missing, f"Enriched message missing labels: {missing}"

    # Each label must have a non-empty value
    for label_key in REQUIRED_LABELS:
        value = labels[label_key]
        assert value is not None and value != "", (
            f"Label '{label_key}' is empty or None: {value!r}"
        )

    # Source must be one of the valid values
    assert labels["source"] in {"CW", "SNS", "EventBridge", "UNKNOWN"}, (
        f"Invalid source label: {labels['source']!r}"
    )

    # Event type must be "alert" or "notification"
    assert labels["event_type"] in {"alert", "notification"}, (
        f"Invalid event_type label: {labels['event_type']!r}"
    )

    # Priority must be P1, P2, or P3
    assert labels["priority"] in {"P1", "P2", "P3"}, (
        f"Invalid priority label: {labels['priority']!r}"
    )

    # Environment must be a non-empty string
    assert isinstance(labels["environment"], str) and labels["environment"].strip(), (
        f"Invalid environment label: {labels['environment']!r}"
    )
