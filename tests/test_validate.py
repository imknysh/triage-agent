"""Unit tests for the validate node."""

from nodes.validate import validate_node, route_validation


class TestValidateNode:
    def test_valid_dict_message(self):
        state = {"raw_message": {"AlarmName": "cpu-high"}}
        result = validate_node(state)
        assert result == {"is_valid": True}

    def test_empty_dict_is_valid(self):
        state = {"raw_message": {}}
        result = validate_node(state)
        assert result == {"is_valid": True}

    def test_missing_raw_message(self):
        state = {}
        result = validate_node(state)
        assert result["is_valid"] is False
        assert "missing" in result["error"]

    def test_raw_message_is_none(self):
        state = {"raw_message": None}
        result = validate_node(state)
        assert result["is_valid"] is False
        assert "missing" in result["error"]

    def test_raw_message_is_string(self):
        state = {"raw_message": "not a dict"}
        result = validate_node(state)
        assert result["is_valid"] is False
        assert "str" in result["error"]

    def test_raw_message_is_list(self):
        state = {"raw_message": [1, 2, 3]}
        result = validate_node(state)
        assert result["is_valid"] is False
        assert "list" in result["error"]

    def test_raw_message_is_int(self):
        state = {"raw_message": 42}
        result = validate_node(state)
        assert result["is_valid"] is False
        assert "int" in result["error"]


class TestRouteValidation:
    def test_routes_to_label_source_when_valid(self):
        state = {"is_valid": True}
        assert route_validation(state) == "label_source"

    def test_routes_to_end_when_invalid(self):
        state = {"is_valid": False}
        assert route_validation(state) == "__end__"

    def test_routes_to_end_when_is_valid_missing(self):
        state = {}
        assert route_validation(state) == "__end__"
