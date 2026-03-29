"""Label event type node for the alert triage LangGraph workflow.

Uses a factory function pattern so the LLM client and system prompt
are captured in a closure, keeping the node signature compatible with
LangGraph (state in, partial state out).
"""

import json
import logging

from models import TriageState

logger = logging.getLogger(__name__)

_VALID_EVENT_TYPES = {"alert", "notification"}


def _parse_event_type(response_text: str) -> str | None:
    """Parse the event_type field from an LLM JSON response.

    Returns the event_type string if valid, or None if parsing fails
    or the value is not in the allowed set.
    """
    try:
        data = json.loads(response_text)
        event_type = data.get("event_type", "").strip().lower()
        if event_type in _VALID_EVENT_TYPES:
            return event_type
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def create_label_event_type_node(llm, system_prompt: str):
    """Factory that returns a label_event_type node function.

    Args:
        llm: A LangChain chat model instance.
        system_prompt: The system prompt instructing the LLM how to classify.

    Returns:
        A node function ``(TriageState) -> dict`` suitable for LangGraph.
    """

    def label_event_type_node(state: TriageState) -> dict:
        """Classify the event type of the alert message via LLM.

        Invokes the LLM with the system prompt and raw message content.
        Validates the response is "alert" or "notification".  Retries
        once on invalid output.  Raises ``ValueError`` if still invalid
        after the retry.
        """
        raw_message = state.get("raw_message", {})
        user_content = json.dumps(raw_message)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        max_attempts = 2  # initial + 1 retry
        response_text = ""
        for attempt in range(1, max_attempts + 1):
            try:
                response = llm.invoke(messages)
                response_text = response.content if hasattr(response, "content") else str(response)
            except Exception as exc:
                logger.error(
                    "LLM invocation failed (attempt %d/%d): %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                continue

            event_type = _parse_event_type(response_text)
            if event_type is not None:
                return {"labels": {"event_type": event_type}}

            logger.warning(
                "Invalid event_type from LLM (attempt %d/%d): %s",
                attempt,
                max_attempts,
                response_text,
            )

        raise ValueError(
            f"LLM returned invalid event_type after {max_attempts} attempts. "
            f"Last response: {response_text}"
        )

    return label_event_type_node
