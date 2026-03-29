"""Unit tests for environment extraction labeler."""

from labelers.environment import extract_environment


class TestExplicitEnvironmentFields:
    """Step 1: Explicit environment/env/environment_id fields."""

    def test_top_level_environment_field(self):
        msg = {"environment": "production", "AlarmName": "test"}
        assert extract_environment(msg) == "production"

    def test_top_level_env_field(self):
        msg = {"env": "staging"}
        assert extract_environment(msg) == "staging"

    def test_top_level_environment_id_field(self):
        msg = {"environment_id": "env-12345"}
        assert extract_environment(msg) == "env-12345"

    def test_nested_environment_in_detail(self):
        msg = {"detail": {"environment": "dev"}, "source": "custom"}
        assert extract_environment(msg) == "dev"

    def test_nested_env_in_detail(self):
        msg = {"detail": {"env": "qa"}, "source": "custom"}
        assert extract_environment(msg) == "qa"

    def test_nested_environment_id_in_detail(self):
        msg = {"detail": {"environment_id": "env-99"}, "source": "custom"}
        assert extract_environment(msg) == "env-99"

    def test_top_level_takes_precedence_over_nested(self):
        msg = {"environment": "prod", "detail": {"environment": "dev"}}
        assert extract_environment(msg) == "prod"

    def test_empty_string_environment_skipped(self):
        msg = {"environment": "", "env": "staging"}
        assert extract_environment(msg) == "staging"

    def test_non_string_environment_skipped(self):
        msg = {"environment": 123, "env": "staging"}
        assert extract_environment(msg) == "staging"


class TestArnAccountExtraction:
    """Step 2: AWS account ID from ARN fields."""

    def test_topic_arn_extraction(self):
        msg = {"TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic", "Type": "Notification"}
        assert extract_environment(msg) == "123456789012"

    def test_source_arn_extraction(self):
        msg = {"Source": "arn:aws:events:us-west-2:987654321098:rule/MyRule"}
        assert extract_environment(msg) == "987654321098"

    def test_eventbridge_detail_account(self):
        msg = {
            "source": "aws.ec2",
            "detail-type": "EC2 Instance State-change",
            "detail": {"account": "111222333444"},
        }
        assert extract_environment(msg) == "111222333444"

    def test_topic_arn_takes_precedence_over_detail_account(self):
        msg = {
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:Topic",
            "detail": {"account": "999888777666"},
        }
        assert extract_environment(msg) == "123456789012"

    def test_invalid_arn_falls_through(self):
        msg = {"TopicArn": "not-an-arn", "detail": {"account": "111222333444"}}
        assert extract_environment(msg) == "111222333444"


class TestFallbackToUnknown:
    """Step 3: Fall back to UNKNOWN."""

    def test_empty_message(self):
        assert extract_environment({}) == "UNKNOWN"

    def test_no_env_fields_no_arns(self):
        msg = {"AlarmName": "test", "NewStateValue": "ALARM"}
        assert extract_environment(msg) == "UNKNOWN"

    def test_detail_without_env_or_account(self):
        msg = {"detail": {"instance_id": "i-12345"}, "source": "custom"}
        assert extract_environment(msg) == "UNKNOWN"

    def test_non_dict_detail_ignored(self):
        msg = {"detail": "not-a-dict"}
        assert extract_environment(msg) == "UNKNOWN"
