"""Label source node for the alert triage LangGraph workflow."""

from labelers.source import detect_source
from models import TriageState


def label_source_node(state: TriageState) -> dict:
    """Detect the source of the alert and update labels.source.

    Calls detect_source() on the raw_message and returns a partial
    state update with the source label.
    """
    raw_message = state.get("raw_message", {})
    source = detect_source(raw_message)
    return {"labels": {"source": source}}
