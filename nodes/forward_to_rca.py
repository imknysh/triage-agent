"""Forward to RCA node for the alert triage LangGraph workflow."""

from forwarder import forward_to_rca
from models import TriageState


def create_forward_to_rca_node(rca_url: str):
    """Factory that returns a forward_to_rca node bound to the given RCA URL.

    The returned node builds an enriched message from state (raw_message +
    labels), forwards it to the RCA agent via A2A protocol, and updates
    the forwarded / forward_error fields accordingly.
    """

    def forward_to_rca_node(state: TriageState) -> dict:
        enriched_message = {
            "original_message": state.get("raw_message", {}),
            "labels": state.get("labels", {}),
        }

        success = forward_to_rca(enriched_message, rca_url)

        if success:
            return {"forwarded": True}
        return {
            "forwarded": False,
            "forward_error": "Failed to forward to RCA agent after retries",
        }

    return forward_to_rca_node
