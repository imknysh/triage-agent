"""A2A Forwarder — wraps enriched alerts in A2A JSON-RPC envelopes and forwards to the RCA agent."""

import json
import logging
import time
import uuid

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]


def build_a2a_message(enriched_message: dict) -> dict:
    """Wrap enriched alert as an A2A JSON-RPC message/send request."""
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": json.dumps(enriched_message),
                    }
                ],
            },
        },
    }


def forward_to_rca(enriched_message: dict, rca_url: str) -> bool:
    """Forward an enriched alert to the RCA agent via A2A protocol.

    Builds an A2A JSON-RPC envelope, POSTs it to the RCA agent's root endpoint,
    and retries up to 3 times with exponential backoff (1 s, 2 s, 4 s)
    on non-2xx responses or request errors.

    Returns True on success, False after all retries are exhausted.
    """
    message = build_a2a_message(enriched_message)
    url = rca_url.rstrip("/")

    for attempt in range(MAX_RETRIES):
        try:
            response = httpx.post(url, json=message, timeout=10)
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

    logger.error(
        "All %d attempts to forward to RCA failed. Enriched message: %s",
        MAX_RETRIES,
        enriched_message,
    )
    return False
