"""Unit tests for the label_environment node."""

from nodes.label_environment import label_environment_node


def test_explicit_environment_field():
    state = {"raw_message": {"environment": "production"}}
    result = label_environment_node(state)
    assert result == {"labels": {"environment": "production"}}


def test_explicit_env_field():
    state = {"raw_message": {"env": "staging"}}
    result = label_environment_node(state)
    assert result == {"labels": {"environment": "staging"}}


def test_explicit_environment_id_field():
    state = {"raw_message": {"environment_id": "env-123"}}
    result = label_environment_node(state)
    assert result == {"labels": {"environment": "env-123"}}


def test_nested_environment_in_detail():
    state = {"raw_message": {"detail": {"environment": "dev"}}}
    result = label_environment_node(state)
    assert result == {"labels": {"environment": "dev"}}


def test_account_from_topic_arn():
    state = {
        "raw_message": {
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic"
        }
    }
    result = label_environment_node(state)
    assert result == {"labels": {"environment": "123456789012"}}


def test_account_from_eventbridge_detail():
    state = {"raw_message": {"detail": {"account": "987654321098"}}}
    result = label_environment_node(state)
    assert result == {"labels": {"environment": "987654321098"}}


def test_unknown_fallback():
    state = {"raw_message": {"foo": "bar"}}
    result = label_environment_node(state)
    assert result == {"labels": {"environment": "UNKNOWN"}}


def test_empty_message():
    state = {"raw_message": {}}
    result = label_environment_node(state)
    assert result == {"labels": {"environment": "UNKNOWN"}}


def test_missing_raw_message_defaults_to_empty():
    state = {}
    result = label_environment_node(state)
    assert result == {"labels": {"environment": "UNKNOWN"}}
