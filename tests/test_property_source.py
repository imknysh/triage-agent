# Feature: alert-triage-agent, Property 3: Source label correctness
# **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

from hypothesis import given, settings, strategies as st
from labelers.source import detect_source


# --- Custom Hypothesis Strategies ---


def cloudwatch_message():
    """Generate realistic CloudWatch alarm messages.

    CloudWatch messages are detected by:
    - AlarmName + NewStateValue fields (native alarm format), OR
    - source == "aws.cloudwatch" (EventBridge-routed CloudWatch events)
    """
    native_alarm = st.fixed_dictionaries({
        "AlarmName": st.text(min_size=1, max_size=50),
        "NewStateValue": st.sampled_from(["ALARM", "OK", "INSUFFICIENT_DATA"]),
        "NewStateReason": st.text(min_size=1, max_size=100),
        "StateChangeTime": st.text(min_size=1, max_size=30),
    })
    eventbridge_routed = st.fixed_dictionaries({
        "source": st.just("aws.cloudwatch"),
        "detail-type": st.text(min_size=1, max_size=60),
        "detail": st.fixed_dictionaries({
            "alarmName": st.text(min_size=1, max_size=50),
        }),
    })
    return st.one_of(native_alarm, eventbridge_routed)


def sns_message():
    """Generate realistic SNS notification messages.

    SNS messages are detected by Type == "Notification" and TopicArn present.
    """
    return st.fixed_dictionaries({
        "Type": st.just("Notification"),
        "TopicArn": st.from_regex(
            r"arn:aws:sns:us-east-1:[0-9]{12}:[a-zA-Z0-9_-]+", fullmatch=True
        ),
        "Subject": st.text(min_size=1, max_size=80),
        "Message": st.text(min_size=1, max_size=200),
    })


def eventbridge_message():
    """Generate realistic EventBridge messages.

    EventBridge messages are detected by source + detail-type + detail fields.
    Source must NOT be "aws.cloudwatch" (those are classified as CW).
    """
    non_cloudwatch_source = st.from_regex(
        r"aws\.[a-z]+", fullmatch=True
    ).filter(lambda s: s != "aws.cloudwatch")

    return st.fixed_dictionaries({
        "source": non_cloudwatch_source,
        "detail-type": st.text(min_size=1, max_size=60),
        "detail": st.fixed_dictionaries({
            "status": st.text(min_size=1, max_size=20),
        }),
        "account": st.from_regex(r"[0-9]{12}", fullmatch=True),
        "region": st.sampled_from(["us-east-1", "us-west-2", "eu-west-1"]),
    })


def unknown_message():
    """Generate valid JSON dicts that don't match any known source pattern.

    Avoids keys that would trigger CloudWatch, SNS, or EventBridge detection.
    """
    return st.fixed_dictionaries({
        "id": st.text(min_size=1, max_size=30),
        "data": st.text(min_size=1, max_size=100),
        "timestamp": st.text(min_size=1, max_size=30),
    })


# --- Property Tests ---


@settings(max_examples=100)
@given(msg=cloudwatch_message())
def test_cloudwatch_messages_detected_as_cw(msg):
    """For any CloudWatch-structured message, detect_source returns 'CW'."""
    assert detect_source(msg) == "CW"


@settings(max_examples=100)
@given(msg=sns_message())
def test_sns_messages_detected_as_sns(msg):
    """For any SNS-structured message, detect_source returns 'SNS'."""
    assert detect_source(msg) == "SNS"


@settings(max_examples=100)
@given(msg=eventbridge_message())
def test_eventbridge_messages_detected_as_eventbridge(msg):
    """For any EventBridge-structured message (non-CloudWatch source),
    detect_source returns 'EventBridge'."""
    assert detect_source(msg) == "EventBridge"


@settings(max_examples=100)
@given(msg=unknown_message())
def test_unknown_messages_detected_as_unknown(msg):
    """For any message not matching known patterns, detect_source returns 'UNKNOWN'."""
    assert detect_source(msg) == "UNKNOWN"
