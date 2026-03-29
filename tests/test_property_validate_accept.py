# Feature: alert-triage-agent, Property 1: Valid JSON acceptance
# **Validates: Requirements 1.1, 1.3**

from hypothesis import given, settings, strategies as st
from nodes.validate import validate_node


# --- Custom Hypothesis Strategy ---

# Strategy that generates random valid JSON-compatible dicts.
# Uses recursive structures to cover nested dicts, lists, and primitive values.
json_primitives = st.none() | st.booleans() | st.integers() | st.floats(
    allow_nan=False, allow_infinity=False
) | st.text(max_size=50)

json_values = st.recursive(
    json_primitives,
    lambda children: st.lists(children, max_size=5) | st.dictionaries(
        st.text(max_size=20), children, max_size=5
    ),
    max_leaves=15,
)

valid_json_dicts = st.dictionaries(
    st.text(max_size=20),
    json_values,
    min_size=0,
    max_size=10,
)


# --- Property Test ---


@settings(max_examples=100)
@given(msg=valid_json_dicts)
def test_valid_json_dicts_are_accepted(msg):
    """For any valid JSON dict, validate_node should accept it (is_valid=True, no error)."""
    state = {"raw_message": msg}
    result = validate_node(state)
    assert result["is_valid"] is True
    assert "error" not in result
