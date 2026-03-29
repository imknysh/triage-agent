# Alert Triage Agent

A LangGraph-based AI agent that ingests JSON alerts from AWS sources (CloudWatch, SNS, EventBridge), labels them with source, event type, priority, and environment, then forwards enriched messages to a downstream RCA agent via A2A protocol.

## Project Structure

```
├── server.py              # FastAPI HTTP server (POST /triage)
├── graph.py               # LangGraph workflow definition
├── models.py              # TriageState and Labels TypedDicts
├── config.py              # Configuration (env vars + validation)
├── llm.py                 # LLM client initialization
├── forwarder.py           # A2A forwarder with retry logic
├── prompt_loader.py       # System prompt loader (URL → file → default)
├── nodes/                 # LangGraph node functions
│   ├── validate.py        # JSON validation + routing
│   ├── label_source.py    # Deterministic source detection
│   ├── label_event_type.py # LLM-based event type classification
│   ├── label_priority.py  # LLM-based priority assignment
│   ├── label_environment.py # Environment extraction
│   └── forward_to_rca.py  # Forward enriched message to RCA agent
├── labelers/              # Deterministic labeling logic
│   ├── source.py          # Source detection (CW, SNS, EventBridge)
│   └── environment.py     # Environment extraction (env fields → ARN → UNKNOWN)
├── prompts/
│   └── system_prompt.txt  # Default LLM system prompt
├── tests/                 # Unit + property-based tests (174 tests)
├── k8s/
│   └── kagent.yaml        # Kubernetes deployment template
├── Dockerfile
└── requirements.txt
```

## Pipeline

```
POST /triage → validate → label_source → label_event_type (LLM)
             → label_priority (LLM) → label_environment → forward_to_rca
```

Invalid JSON short-circuits to an error response. Valid messages flow through all six nodes and get forwarded to the RCA agent with retry logic (3 attempts, exponential backoff).

## Prerequisites

- Python 3.12+
- An OpenAI API key (or compatible provider)

## Local Development Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set required environment variables:

```bash
export RCA_AGENT_URL="http://localhost:9090"   # RCA agent endpoint (required)
export LLM_API_KEY="sk-your-openai-key"        # OpenAI API key
```

4. Run the server:

```bash
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

5. Send a test request:

```bash
curl -X POST http://localhost:8080/triage \
  -H "Content-Type: application/json" \
  -d '{
    "AlarmName": "HighCPUAlarm",
    "NewStateValue": "ALARM",
    "NewStateReason": "Threshold crossed: CPU > 90%"
  }'
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `RCA_AGENT_URL` | No | `http://localhost:9090` | RCA agent endpoint URL |
| `LLM_API_KEY` | Yes* | `""` | API key for the LLM provider |
| `LLM_PROVIDER` | No | `openai` | LLM provider (`openai`, `azure`, `anthropic`) |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model name |
| `SERVICE_PORT` | No | `8080` | Server port |
| `SYSTEM_PROMPT_URL` | No | — | HTTP URL to fetch system prompt from |
| `SYSTEM_PROMPT_FILE` | No | — | File path for system prompt (e.g. ConfigMap mount) |
| `LOG_LEVEL` | No | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

*Required when using an external LLM provider.

The system prompt is loaded with a fallback chain: `SYSTEM_PROMPT_URL` → `SYSTEM_PROMPT_FILE` → `prompts/system_prompt.txt`.

## Running Tests

```bash
python3 -m pytest tests/ -v
```

The test suite includes 174 tests: unit tests for each module and property-based tests (using Hypothesis) that verify correctness properties across randomly generated inputs.

## Docker

Build and run:

```bash
docker build -t alert-triage-agent .
docker run -p 8080:8080 \
  -e RCA_AGENT_URL=http://rca-agent:8080 \
  -e LLM_API_KEY=sk-your-key \
  alert-triage-agent
```

## Kubernetes (kagent)

The agent is deployed as a [kagent](https://github.com/kagent-dev/kagent) `Agent` custom resource (BYO type). Requires kagent installed on your cluster.

```bash
# Edit k8s/kagent.yaml to set your API key and RCA URL, then:
kubectl apply -f k8s/kagent.yaml
```

This creates the necessary Secrets and a kagent `Agent` resource that runs the containerized agent in the `kagent` namespace.
