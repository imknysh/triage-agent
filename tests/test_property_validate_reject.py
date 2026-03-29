# Feature: alert-triage-agent, Property 2: Invalid JSON rejection
# **Validates: Requirements 1.2**

from hypothesis import given, settings, strategies as st
from nodes.validate import validate_node


# --- Custom Hypothesis Strategies ---

# Strategy that generates random non-dict values: strings, ints, lists, None,
# booleans, and floats. These represent inputs that are not valid JSON objects.
non_dict_values = (
    st.text(max_size=100)
    | st.integers()
    | st.lists(st.integers(), max_size=5)
    | st.none()
    | st.booleans()
    | st.floats(allow_nan=False, allow_infinity=False)
)


# --- Property Tests ---


@settings(max_examples=100)
@given(value=non_dict_values)
def test_non_dict_raw_message_is_rejected(value):
    """For any non-dict raw_message, validate_node should reject it with
    is_valid=False and a non-empty descriptive error string, and no labels
    should be produced."""
    state = {"raw_message": value}
    result = validate_node(state)
    assert result["is_valid"] is False
    assert "error" in result
    assert isinstance(result["error"], str)
    assert len(result["error"]) > 0
    assert "labels" not in result


@settings(max_examples=100)
@given(data=st.data())
def test_missing_raw_message_is_rejected(data):
    """When raw_message is missing from state, validate_node should reject it
    with is_valid=False and a non-empty descriptive error string, and no labels
    should be produced."""
    state = {}
    result = validate_node(state)
    assert result["is_valid"] is False
    assert "error" in result
    assert isinstance(result["error"], str)
    assert len(result["error"]) > 0
    assert "labels" not in result
