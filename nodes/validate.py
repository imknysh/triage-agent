"""Validate node for the alert triage LangGraph workflow."""

from models import TriageState


def validate_node(state: TriageState) -> dict:
    """Check that raw_message exists and is a valid dict.

    Returns a partial state update with is_valid and optionally error.
    """
    raw_message = state.get("raw_message")

    if raw_message is None:
        return {"is_valid": False, "error": "raw_message is missing from state"}

    if not isinstance(raw_message, dict):
        return {
            "is_valid": False,
            "error": f"raw_message must be a dict, got {type(raw_message).__name__}",
        }

    return {"is_valid": True}


def route_validation(state: TriageState) -> str:
    """Conditional edge: route to label_source on valid input, END otherwise."""
    if state.get("is_valid"):
        return "label_source"
    return "__end__"
