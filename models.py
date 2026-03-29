from typing import Annotated, TypedDict, Optional, Literal


class Labels(TypedDict, total=False):
    source: Literal["CW", "SNS", "EventBridge", "UNKNOWN"]
    event_type: Literal["alert", "notification"]
    priority: Literal["P1", "P2", "P3"]
    environment: str


def _merge_labels(current: Labels, update: Labels) -> Labels:
    """Merge partial label dicts so each node's output accumulates."""
    merged = {**current, **update}
    return merged  # type: ignore[return-value]


class TriageState(TypedDict, total=False):
    raw_message: dict
    is_valid: bool
    error: Optional[str]
    labels: Annotated[Labels, _merge_labels]
    forwarded: bool
    forward_error: Optional[str]
    retry_count: int
