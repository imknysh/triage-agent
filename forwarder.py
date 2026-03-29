"""A2A Forwarder — wraps enriched alerts in A2A task envelopes and forwards to the RCA agent."""

import logging
import time
import uuid

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]


def _generate_task_id() -> str:
    """Generate a unique task ID."""
    return str(uuid.uuid4())


def build_a2a_task(enriched_message: dict) -> dict:
    """Wrap enriched alert as an A2A Task with JSON-RPC structure."""
    return {
        "jsonrpc": "2.0",
        "method": "tasks/send",
        "params": {
            "id": _generate_task_id(),
            "message": {
                "role": "user",
                "parts": [
                    {
                        "type": "data",
                        "data": enriched_message,
                    }
                ],
            },
        },
    }


def forward_to_rca(enriched_message: dict, rca_url: str) -> bool:
    """Forward an enriched alert to the RCA agent via A2A protocol.

    Builds an A2A task envelope, POSTs it to ``{rca_url}/tasks/send``,
    and retries up to 3 times with exponential backoff (1 s, 2 s, 4 s)
    on non-2xx responses or request errors.

    Returns True on success, False after all retries are exhausted.
    """
    task = build_a2a_task(enriched_message)
    url = f"{rca_url.rstrip('/')}/tasks/send"

    for attempt in range(MAX_RETRIES):
        try:
            response = httpx.post(url, json=task, timeout=10)
            response.raise_for_status()
            return True
        except Exception as exc:
            logger.error(
                "Attempt %d/%d to forward to RCA failed: %s",
                attempt + 1,
                MAX_RETRIES,
                exc,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_SECONDS[attempt])

    # All retries exhausted — log the full enriched message for manual review
    logger.error(
        "All %d attempts to forward to RCA failed. Enriched message: %s",
        MAX_RETRIES,
        enriched_message,
    )
    return False
