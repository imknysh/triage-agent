"""Tests for the FastAPI triage server."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient


def _make_mock_graph():
    """Create a mock compiled graph with an ainvoke method."""
    return AsyncMock()


@pytest.fixture
def mock_graph():
    return _make_mock_graph()


@pytest.fixture
def client(mock_graph):
    """Patch startup dependencies and return a TestClient."""
    fake_config = MagicMock()
    fake_config.rca_agent_url = "http://rca:8080"

    with (
        patch("server.load_config", return_value=fake_config),
        patch("server.load_system_prompt", return_value="You are a triage agent."),
        patch("server.create_llm_client", return_value=MagicMock()),
        patch("server.build_triage_graph", return_value=mock_graph),
    ):
        from server import app
        with TestClient(app) as tc:
            yield tc


# --- Startup tests ---

def test_startup_fails_on_bad_config():
    """Config is loaded at startup; failure propagates."""
    with patch("server.load_config", side_effect=ValueError("bad config")):
        from server import app
        with pytest.raises(ValueError, match="bad config"):
            with TestClient(app):
                _ = "startup should fail"


def test_startup_fails_on_missing_prompt():
    """System prompt is loaded at startup; failure propagates."""
    fake_config = MagicMock()
    fake_config.rca_agent_url = "http://rca:8080"
    with (
        patch("server.load_config", return_value=fake_config),
        patch("server.load_system_prompt", side_effect=RuntimeError("no prompt")),
    ):
        from server import app
        with pytest.raises(RuntimeError, match="no prompt"):
            with TestClient(app):
                _ = "startup should fail"


# --- POST /triage tests ---

def test_triage_returns_200_on_success(client, mock_graph):
    mock_graph.ainvoke.return_value = {
        "raw_message": {"AlarmName": "cpu"},
        "is_valid": True,
        "labels": {"source": "CW", "event_type": "alert", "priority": "P1", "environment": "prod"},
        "forwarded": True,
    }
    resp = client.post("/triage", content=json.dumps({"AlarmName": "cpu"}))
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["labels"]["source"] == "CW"


def test_triage_returns_400_on_invalid_json(client, mock_graph):
    resp = client.post("/triage", content="not json {{{")
    assert resp.status_code == 400
    assert "Invalid JSON" in resp.json()["error"]


def test_triage_returns_400_when_graph_says_invalid(client, mock_graph):
    mock_graph.ainvoke.return_value = {
        "raw_message": "bad",
        "is_valid": False,
        "error": "raw_message is not a dict",
    }
    resp = client.post("/triage", content=json.dumps("bad"))
    assert resp.status_code == 400
    assert "not a dict" in resp.json()["error"]


def test_triage_returns_500_on_processing_error(client, mock_graph):
    mock_graph.ainvoke.side_effect = RuntimeError("boom")
    resp = client.post("/triage", content=json.dumps({"key": "val"}))
    assert resp.status_code == 500
    assert "Processing error" in resp.json()["error"]
