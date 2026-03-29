"""Unit tests for the forward_to_rca node."""

from unittest.mock import patch

from nodes.forward_to_rca import create_forward_to_rca_node


class TestForwardToRcaNode:
    def _make_state(self, raw_message=None, labels=None):
        state = {}
        if raw_message is not None:
            state["raw_message"] = raw_message
        if labels is not None:
            state["labels"] = labels
        return state

    @patch("nodes.forward_to_rca.forward_to_rca", return_value=True)
    def test_success_sets_forwarded_true(self, mock_fwd):
        node = create_forward_to_rca_node("http://rca:8080")
        state = self._make_state(
            raw_message={"AlarmName": "cpu"},
            labels={"source": "CW", "event_type": "alert", "priority": "P1", "environment": "prod"},
        )
        result = node(state)

        assert result == {"forwarded": True}
        mock_fwd.assert_called_once()
        enriched = mock_fwd.call_args[0][0]
        assert enriched["original_message"] == {"AlarmName": "cpu"}
        assert enriched["labels"]["source"] == "CW"

    @patch("nodes.forward_to_rca.forward_to_rca", return_value=False)
    def test_failure_sets_forwarded_false_with_error(self, mock_fwd):
        node = create_forward_to_rca_node("http://rca:8080")
        state = self._make_state(
            raw_message={"foo": "bar"},
            labels={"source": "UNKNOWN"},
        )
        result = node(state)

        assert result["forwarded"] is False
        assert "forward_error" in result
        assert "Failed to forward" in result["forward_error"]

    @patch("nodes.forward_to_rca.forward_to_rca", return_value=True)
    def test_enriched_message_contains_raw_and_labels(self, mock_fwd):
        node = create_forward_to_rca_node("http://rca:9090")
        raw = {"detail-type": "EC2 State Change"}
        labels = {"source": "EventBridge", "priority": "P2"}
        state = self._make_state(raw_message=raw, labels=labels)
        node(state)

        enriched = mock_fwd.call_args[0][0]
        assert enriched["original_message"] is raw
        assert enriched["labels"] is labels

    @patch("nodes.forward_to_rca.forward_to_rca", return_value=True)
    def test_rca_url_passed_to_forwarder(self, mock_fwd):
        url = "http://my-rca:3000"
        node = create_forward_to_rca_node(url)
        node(self._make_state(raw_message={}, labels={}))

        assert mock_fwd.call_args[0][1] == url

    @patch("nodes.forward_to_rca.forward_to_rca", return_value=True)
    def test_defaults_when_state_missing_fields(self, mock_fwd):
        node = create_forward_to_rca_node("http://rca:8080")
        result = node({})

        assert result == {"forwarded": True}
        enriched = mock_fwd.call_args[0][0]
        assert enriched["original_message"] == {}
        assert enriched["labels"] == {}
