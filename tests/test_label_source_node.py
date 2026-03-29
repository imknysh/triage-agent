"""Unit tests for the label_source node."""

from nodes.label_source import label_source_node


def test_cloudwatch_alarm_message():
    state = {"raw_message": {"AlarmName": "HighCPU", "NewStateValue": "ALARM"}}
    result = label_source_node(state)
    assert result == {"labels": {"source": "CW"}}


def test_cloudwatch_eventbridge_routed():
    state = {"raw_message": {"source": "aws.cloudwatch", "detail": {}}}
    result = label_source_node(state)
    assert result == {"labels": {"source": "CW"}}


def test_sns_notification():
    state = {
        "raw_message": {
            "Type": "Notification",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic",
        }
    }
    result = label_source_node(state)
    assert result == {"labels": {"source": "SNS"}}


def test_eventbridge_message():
    state = {
        "raw_message": {
            "source": "aws.ec2",
            "detail-type": "EC2 Instance State-change",
            "detail": {"instance-id": "i-1234"},
        }
    }
    result = label_source_node(state)
    assert result == {"labels": {"source": "EventBridge"}}


def test_unknown_message():
    state = {"raw_message": {"foo": "bar"}}
    result = label_source_node(state)
    assert result == {"labels": {"source": "UNKNOWN"}}


def test_empty_message():
    state = {"raw_message": {}}
    result = label_source_node(state)
    assert result == {"labels": {"source": "UNKNOWN"}}


def test_missing_raw_message_defaults_to_empty():
    state = {}
    result = label_source_node(state)
    assert result == {"labels": {"source": "UNKNOWN"}}
