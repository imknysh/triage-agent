"""Label environment node for the alert triage LangGraph workflow."""

from labelers.environment import extract_environment
from models import TriageState


def label_environment_node(state: TriageState) -> dict:
    """Extract the environment from the alert and update labels.environment.

    Calls extract_environment() on the raw_message and returns a partial
    state update with the environment label.
    """
    raw_message = state.get("raw_message", {})
    environment = extract_environment(raw_message)
    return {"labels": {"environment": environment}}
