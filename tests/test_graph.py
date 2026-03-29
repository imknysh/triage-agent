"""Tests for the triage graph builder."""

from unittest.mock import MagicMock, patch

from graph import build_triage_graph


class TestBuildTriageGraph:
    """Verify build_triage_graph wires nodes and edges correctly."""

    def _build(self):
        llm = MagicMock()
        return build_triage_graph(llm, system_prompt="test prompt", rca_url="http://rca:8080")

    def test_returns_compiled_graph(self):
        compiled = self._build()
        # CompiledStateGraph exposes a .get_graph() helper
        assert compiled is not None

    def test_entry_point_is_validate(self):
        compiled = self._build()
        g = compiled.get_graph()
        # The __start__ node should have an edge to validate
        start_edges = [e.target for e in g.edges if e.source == "__start__"]
        assert "validate" in start_edges

    def test_all_six_nodes_present(self):
        compiled = self._build()
        g = compiled.get_graph()
        node_ids = set(g.nodes.keys())
        expected = {
            "validate",
            "label_source",
            "label_event_type",
            "label_priority",
            "label_environment",
            "forward_to_rca",
        }
        assert expected.issubset(node_ids)

    def test_sequential_edges(self):
        compiled = self._build()
        g = compiled.get_graph()
        edge_pairs = {(e.source, e.target) for e in g.edges}
        assert ("label_source", "label_event_type") in edge_pairs
        assert ("label_event_type", "label_priority") in edge_pairs
        assert ("label_priority", "label_environment") in edge_pairs
        assert ("label_environment", "forward_to_rca") in edge_pairs
        assert ("forward_to_rca", "__end__") in edge_pairs

    def test_validate_has_conditional_edge(self):
        compiled = self._build()
        g = compiled.get_graph()
        validate_targets = {e.target for e in g.edges if e.source == "validate"}
        # Should route to label_source (valid) or __end__ (invalid)
        assert "label_source" in validate_targets
        assert "__end__" in validate_targets

    @patch("nodes.forward_to_rca.forward_to_rca", return_value=True)
    def test_invoke_valid_message(self, mock_fwd):
        """End-to-end: a valid message should flow through all nodes."""
        # Stub LLM to return valid JSON for event_type and priority
        llm = MagicMock()
        llm.invoke.side_effect = [
            MagicMock(content='{"event_type": "alert"}'),
            MagicMock(content='{"priority": "P1"}'),
        ]
        compiled = build_triage_graph(llm, system_prompt="sp", rca_url="http://rca")
        result = compiled.invoke({"raw_message": {"AlarmName": "cpu", "NewStateValue": "ALARM"}})

        assert result["is_valid"] is True
        assert result["labels"]["source"] == "CW"
        assert result["labels"]["event_type"] == "alert"
        assert result["labels"]["priority"] == "P1"
        assert "environment" in result["labels"]
        assert result["forwarded"] is True

    def test_invoke_invalid_message(self):
        """Invalid input should short-circuit to END without labeling."""
        llm = MagicMock()
        compiled = build_triage_graph(llm, system_prompt="sp", rca_url="http://rca")
        result = compiled.invoke({"raw_message": "not a dict"})

        assert result["is_valid"] is False
        assert "error" in result
        # LLM should never have been called
        llm.invoke.assert_not_called()
