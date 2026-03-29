"""Source detection labeler for alert messages.

Deterministic source detection based on known AWS message structures.
"""


def detect_source(message: dict) -> str:
    """Detect the source of an alert message based on its structure.

    Detection rules (evaluated in order):
    1. CloudWatch: presence of AlarmName + NewStateValue, or source == "aws.cloudwatch"
    2. SNS: Type == "Notification" and TopicArn present
    3. EventBridge: source + detail-type + detail fields (excluding CloudWatch sources)
    4. UNKNOWN: no pattern matched

    Args:
        message: A dictionary representing the alert message.

    Returns:
        One of "CW", "SNS", "EventBridge", or "UNKNOWN".
    """
    # CloudWatch: native alarm format
    if "AlarmName" in message and "NewStateValue" in message:
        return "CW"

    # CloudWatch: EventBridge-routed CloudWatch events
    if message.get("source") == "aws.cloudwatch":
        return "CW"

    # SNS: notification format
    if message.get("Type") == "Notification" and "TopicArn" in message:
        return "SNS"

    # EventBridge: generic event schema (but not CloudWatch, already handled above)
    if "source" in message and "detail-type" in message and "detail" in message:
        return "EventBridge"

    return "UNKNOWN"
