"""HTTP server for the Alert Triage Agent.

Supports two modes:
- KAgent mode (KAGENT_URL set): Uses KAgentApp with A2A protocol, streaming,
  and session persistence via KAgentCheckpointer.
- Standalone mode: Plain FastAPI with POST /triage endpoint.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import load_config
from prompt_loader import load_system_prompt
from llm import create_llm_client
from graph import build_triage_graph

# Configure logging from LOG_LEVEL env var (default: INFO)
_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)

# Shared graph instance (set during startup)
_graph = None


def _build_graph():
    """Build the triage graph from config."""
    config = load_config()
    system_prompt = load_system_prompt()
    llm_client = create_llm_client(config)
    return build_triage_graph(llm_client, system_prompt, config.rca_agent_url)


def _load_agent_card() -> dict:
    """Load agent-card.json from .well-known directory."""
    card_path = Path(__file__).parent / ".well-known" / "agent-card.json"
    if card_path.exists():
        return json.loads(card_path.read_text())
    return {
        "name": "alert-triage-agent",
        "description": "Alert Triage Agent",
        "url": f"http://localhost:{os.getenv('PORT', '8080')}",
        "version": "1.0.0",
        "capabilities": {"streaming": True},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [],
    }


def build_kagent_app():
    """Build a KAgentApp for running under kagent framework."""
    from kagent.core import KAgentConfig
    from kagent.langgraph import KAgentApp

    graph = _build_graph()
    agent_card = _load_agent_card()
    config = KAgentConfig()

    app = KAgentApp(
        graph=graph,
        agent_card=agent_card,
        config=config,
        tracing=os.getenv("OTEL_TRACING_ENABLED", "false").lower() == "true",
    )
    return app.build()


# --- Standalone FastAPI app (when not using KAgentApp) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load config, prompt, LLM client, and graph."""
    global _graph
    _graph = _build_graph()
    app.state.graph = _graph
    logger.info("Triage graph initialized")
    yield


standalone_app = FastAPI(lifespan=lifespan)

# Serve .well-known/agent-card.json for A2A discovery
_well_known_dir = Path(__file__).parent / ".well-known"
if _well_known_dir.is_dir():
    standalone_app.mount(
        "/.well-known",
        StaticFiles(directory=str(_well_known_dir)),
        name="well-known",
    )


@standalone_app.post("/triage")
async def triage(request: Request):
    """Accept a raw JSON alert, run the triage graph, return the result."""
    client_ip = request.client.host if request.client else "unknown"

    try:
        body = await request.body()
        raw_message = json.loads(body)
    except Exception:
        logger.warning(
            "src=%s status=400 error='Invalid JSON' body=%s",
            client_ip,
            body[:500] if body else b"",
        )
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON in request body"},
        )

    logger.info("src=%s body=%s", client_ip, json.dumps(raw_message, default=str)[:1000])

    try:
        result = await request.app.state.graph.ainvoke({"raw_message": raw_message})
    except Exception as exc:
        logger.exception("src=%s status=500 error='%s'", client_ip, exc)
        return JSONResponse(
            status_code=500,
            content={"error": f"Processing error: {str(exc)}"},
        )

    if result.get("is_valid") is False:
        logger.warning("src=%s status=400 error='%s'", client_ip, result.get("error"))
        return JSONResponse(
            status_code=400,
            content={"error": result.get("error", "Validation failed")},
        )

    logger.info(
        "src=%s status=200 labels=%s forwarded=%s",
        client_ip,
        result.get("labels"),
        result.get("forwarded"),
    )
    return JSONResponse(status_code=200, content=result)


# Default app: use KAgentApp if KAGENT_URL is set, otherwise standalone
def _resolve_app():
    if os.getenv("KAGENT_URL"):
        logger.info("KAGENT_URL detected, using KAgentApp mode")
        return build_kagent_app()
    logger.info("Standalone mode (no KAGENT_URL)")
    return standalone_app


app = _resolve_app()
