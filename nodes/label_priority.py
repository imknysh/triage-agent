"""Label priority node for the alert triage LangGraph workflow.

Uses a factory function pattern so the LLM client and system prompt
are captured in a closure, keeping the node signature compatible with
LangGraph (state in, partial state out).
"""

import json
import logging

from models import TriageState

logger = logging.getLogger(__name__)

_VALID_PRIORITIES = {"P1", "P2", "P3"}


def _parse_priority(response_text: str) -> str | None:
    """Parse the priority field from an LLM JSON response.

    Returns the priority string if valid, or None if parsing fails
    or the value is not in the allowed set.
    """
    try:
        data = json.loads(response_text)
        priority = data.get("priority", "").strip().upper()
        if priority in _VALID_PRIORITIES:
            return priority
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def create_label_priority_node(llm, system_prompt: str):
    """Factory that returns a label_priority node function.

    Args:
        llm: A LangChain chat model instance.
        system_prompt: The system prompt instructing the LLM how to classify.

    Returns:
        A node function ``(TriageState) -> dict`` suitable for LangGraph.
    """

    def label_priority_node(state: TriageState) -> dict:
        """Assign priority to the alert message via LLM.

        Invokes the LLM with the system prompt and raw message content.
        Validates the response is "P1", "P2", or "P3".  Retries once on
        invalid output.  Raises ``ValueError`` if still invalid after
        the retry.
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

            priority = _parse_priority(response_text)
            if priority is not None:
                return {"labels": {"priority": priority}}

            logger.warning(
                "Invalid priority from LLM (attempt %d/%d): %s",
                attempt,
                max_attempts,
                response_text,
            )

        raise ValueError(
            f"LLM returned invalid priority after {max_attempts} attempts. "
            f"Last response: {response_text}"
        )

    return label_priority_node
