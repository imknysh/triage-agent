"""FastAPI HTTP server for the Alert Triage Agent.

Exposes a single POST /triage endpoint that accepts raw JSON alert messages,
runs them through the LangGraph triage pipeline, and returns the result.
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup initialisation: load config, prompt, LLM client, and graph."""
    config = load_config()
    system_prompt = load_system_prompt()
    llm = create_llm_client(config)
    app.state.graph = build_triage_graph(llm, system_prompt, config.rca_agent_url)
    yield


app = FastAPI(lifespan=lifespan)

# Serve .well-known/agent-card.json for A2A discovery
_well_known_dir = Path(__file__).parent / ".well-known"
if _well_known_dir.is_dir():
    app.mount("/.well-known", StaticFiles(directory=str(_well_known_dir)), name="well-known")


@app.post("/triage")
async def triage(request: Request):
    """Accept a raw JSON alert, run the triage graph, return the result."""
    client_ip = request.client.host if request.client else "unknown"

    try:
        body = await request.body()
        raw_message = json.loads(body)
    except Exception:
        logger.warning("src=%s status=400 error='Invalid JSON' body=%s", client_ip, body[:500] if body else b"")
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON in request body"},
        )

    logger.info("src=%s body=%s", client_ip, json.dumps(raw_message, default=str)[:1000])

    try:
        result = await app.state.graph.ainvoke({"raw_message": raw_message})
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
