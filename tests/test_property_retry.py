# Feature: alert-triage-agent, Property 8: Retry on RCA agent failure
# **Validates: Requirements 6.2**

from unittest.mock import patch, MagicMock

import httpx
from hypothesis import given, settings, strategies as st

from forwarder import forward_to_rca, MAX_RETRIES


# --- Custom Hypothesis Strategies ---


def enriched_message():
    """Generate random enriched messages with labels and original message."""
    return st.fixed_dictionaries({
        "original_message": st.fixed_dictionaries({
            "id": st.text(min_size=1, max_size=30),
            "data": st.text(min_size=1, max_size=100),
        }),
        "labels": st.fixed_dictionaries({
            "source": st.sampled_from(["CW", "SNS", "EventBridge", "UNKNOWN"]),
            "event_type": st.sampled_from(["alert", "notification"]),
            "priority": st.sampled_from(["P1", "P2", "P3"]),
            "environment": st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
        }),
    })


def rca_url():
    """Generate random but valid-looking RCA agent URLs."""
    return st.from_regex(
        r"http://rca-[a-z]{3,8}:[0-9]{4}", fullmatch=True
    )


# --- Property Tests ---


@settings(max_examples=150)
@given(msg=enriched_message(), url=rca_url())
def test_all_failures_result_in_exactly_max_retries_calls(msg, url):
    """Property 8: When the RCA agent always fails, forward_to_rca must
    call httpx.post exactly MAX_RETRIES (3) times and return False."""

    with patch("forwarder.httpx.post", side_effect=httpx.ConnectError("refused")) as mock_post, \
         patch("forwarder.time.sleep"):
        result = forward_to_rca(msg, url)

    assert result is False, "forward_to_rca should return False when all retries fail"
    assert mock_post.call_count == MAX_RETRIES, (
        f"Expected exactly {MAX_RETRIES} calls, got {mock_post.call_count}"
    )


@settings(max_examples=150)
@given(
    msg=enriched_message(),
    url=rca_url(),
    succeed_on=st.integers(min_value=1, max_value=MAX_RETRIES),
)
def test_success_after_failures_has_correct_call_count(msg, url, succeed_on):
    """Property 8 (partial success): When the RCA agent fails (succeed_on - 1)
    times then succeeds, forward_to_rca returns True and the total call count
    equals succeed_on."""

    failures = [httpx.ConnectError("refused")] * (succeed_on - 1)
    success = MagicMock(status_code=200, raise_for_status=MagicMock())
    side_effects = failures + [success]

    with patch("forwarder.httpx.post", side_effect=side_effects) as mock_post, \
         patch("forwarder.time.sleep"):
        result = forward_to_rca(msg, url)

    assert result is True, (
        f"forward_to_rca should return True when succeeding on attempt {succeed_on}"
    )
    assert mock_post.call_count == succeed_on, (
        f"Expected {succeed_on} calls, got {mock_post.call_count}"
    )
