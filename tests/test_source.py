"""Unit tests for source detection labeler."""

from labelers.source import detect_source


class TestCloudWatchDetection:
    """Tests for CloudWatch source detection."""

    def test_native_alarm_format(self):
        msg = {
            "AlarmName": "HighCPUAlarm",
            "NewStateValue": "ALARM",
            "NewStateReason": "Threshold crossed",
        }
        assert detect_source(msg) == "CW"

    def test_eventbridge_routed_cloudwatch(self):
        msg = {
            "source": "aws.cloudwatch",
            "detail-type": "CloudWatch Alarm State Change",
            "detail": {"alarmName": "HighCPUAlarm"},
        }
        assert detect_source(msg) == "CW"

    def test_cloudwatch_with_extra_fields(self):
        msg = {
            "AlarmName": "DiskSpaceAlarm",
            "NewStateValue": "OK",
            "OldStateValue": "ALARM",
            "Region": "us-east-1",
        }
        assert detect_source(msg) == "CW"


class TestSNSDetection:
    """Tests for SNS source detection."""

    def test_sns_notification(self):
        msg = {
            "Type": "Notification",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic",
            "Message": "Alert triggered",
        }
        assert detect_source(msg) == "SNS"

    def test_sns_without_topic_arn(self):
        """Type=Notification but no TopicArn should not match SNS."""
        msg = {"Type": "Notification", "Message": "something"}
        assert detect_source(msg) == "UNKNOWN"

    def test_sns_wrong_type(self):
        """TopicArn present but Type is not Notification."""
        msg = {
            "Type": "SubscriptionConfirmation",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic",
        }
        assert detect_source(msg) == "UNKNOWN"


class TestEventBridgeDetection:
    """Tests for EventBridge source detection."""

    def test_eventbridge_event(self):
        msg = {
            "source": "aws.ec2",
            "detail-type": "EC2 Instance State-change Notification",
            "detail": {"instance-id": "i-1234567890abcdef0"},
        }
        assert detect_source(msg) == "EventBridge"

    def test_eventbridge_custom_source(self):
        msg = {
            "source": "my.custom.app",
            "detail-type": "OrderPlaced",
            "detail": {"orderId": "12345"},
        }
        assert detect_source(msg) == "EventBridge"

    def test_eventbridge_missing_detail_type(self):
        """Missing detail-type should not match EventBridge."""
        msg = {
            "source": "aws.ec2",
            "detail": {"instance-id": "i-123"},
        }
        assert detect_source(msg) == "UNKNOWN"

    def test_eventbridge_missing_detail(self):
        """Missing detail should not match EventBridge."""
        msg = {
            "source": "aws.ec2",
            "detail-type": "EC2 Instance State-change Notification",
        }
        assert detect_source(msg) == "UNKNOWN"

    def test_cloudwatch_source_not_detected_as_eventbridge(self):
        """EventBridge event with source=aws.cloudwatch should be CW, not EventBridge."""
        msg = {
            "source": "aws.cloudwatch",
            "detail-type": "CloudWatch Alarm State Change",
            "detail": {"alarmName": "TestAlarm"},
        }
        assert detect_source(msg) == "CW"


class TestUnknownDetection:
    """Tests for UNKNOWN source detection."""

    def test_empty_message(self):
        assert detect_source({}) == "UNKNOWN"

    def test_unrecognized_structure(self):
        msg = {"foo": "bar", "baz": 42}
        assert detect_source(msg) == "UNKNOWN"

    def test_partial_cloudwatch_fields(self):
        """Only AlarmName without NewStateValue should be UNKNOWN."""
        msg = {"AlarmName": "TestAlarm"}
        assert detect_source(msg) == "UNKNOWN"
