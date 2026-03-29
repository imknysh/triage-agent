# Implementation Plan: Alert Triage Agent

## Overview

Build a LangGraph-based alert triage agent in Python that ingests JSON alerts from AWS sources (CloudWatch, SNS, EventBridge), labels them with source, event type, priority, and environment, then forwards enriched messages to an RCA agent via A2A protocol. Uses the kagent framework with KAgentCheckpointer for session persistence and KAgentApp for A2A protocol compatibility. Implementation follows a dependency-first build order: data models → configuration → prompt loading → labelers → LLM integration → A2A forwarder → graph nodes → workflow graph → HTTP server → Dockerfile → kagent Agent CRD.

## Tasks

- [x] 1. Set up project structure and data models
  - [x] 1.1 Create project directory structure and `requirements.txt`
    - Create directories: `nodes/`, `labelers/`, `prompts/`, `k8s/`, `tests/`, `.well-known/`
    - Create `requirements.txt` with dependencies: `langgraph`, `langchain-openai`, `langchain-core`, `kagent-langgraph`, `fastapi`, `uvicorn`, `httpx`, `pydantic`, `hypothesis`, `pytest`, `langsmith[otel]`
    - Create `__init__.py` files for `nodes/`, `labelers/`, `tests/` packages
    - _Requirements: 10.3_

  - [x] 1.2 Implement data models (`models.py`)
    - Define `Labels` TypedDict with `source`, `event_type`, `priority`, `environment` fields
    - Define `TriageState` TypedDict with `raw_message`, `is_valid`, `error`, `labels`, `forwarded`, `forward_error`, `retry_count` fields
    - _Requirements: 2.1, 3.1, 4.1, 5.1, 6.1_

  - [x] 1.3 Write property test for enriched message completeness
    - **Property 7: Enriched message completeness**
    - Generate random valid messages that complete the pipeline, verify all 4 labels (source, event_type, priority, environment) and original message are present
    - **Validates: Requirements 6.1**

- [x] 2. Implement configuration and prompt loading
  - [x] 2.1 Implement configuration module (`config.py`)
    - Define `AgentConfig` Pydantic model with fields: `llm_provider`, `llm_model`, `llm_api_key`, `rca_agent_url`, `service_port`, `system_prompt_url`, `system_prompt_file`
    - Implement `load_config()` function that reads from environment variables
    - Validate `rca_agent_url` is present; raise descriptive error if missing
    - Validate LLM configuration; raise descriptive error if invalid
    - Apply defaults: `llm_provider="openai"`, `llm_model="gpt-4o-mini"`, `service_port=8080`
    - _Requirements: 8.1, 8.2, 8.3, 9.1, 9.2_

  - [x] 2.2 Write property test for configuration application
    - **Property 9: Configuration application**
    - Generate valid combinations of `LLM_PROVIDER` and `LLM_MODEL` env vars, verify agent initializes with those values
    - **Validates: Requirements 8.1**

  - [x] 2.3 Write property test for invalid configuration startup failure
    - **Property 10: Invalid configuration startup failure**
    - Generate invalid LLM configs (unsupported provider, malformed model) or missing `RCA_AGENT_URL`, verify startup failure with descriptive error
    - **Validates: Requirements 8.3, 9.2**

  - [x] 2.4 Create system prompt text file (`prompts/system_prompt.txt`)
    - Write a system prompt instructing the LLM to analyze alert messages and determine event type ("alert" or "notification") and priority ("P1", "P2", "P3")
    - Include classification criteria: P1 for outages/critical failures, P2 for degraded performance/warnings, P3 for informational/low-impact
    - _Requirements: 7.1, 7.4_

  - [x] 2.5 Implement system prompt loader (`prompt_loader.py`)
    - Implement `load_system_prompt()` with fallback chain: HTTP URL → file path → default local file
    - Read `SYSTEM_PROMPT_URL` env var; fetch via `httpx.get()` with 10s timeout
    - Read `SYSTEM_PROMPT_FILE` env var; read file via `Path.read_text()`
    - Fall back to `prompts/system_prompt.txt` as default
    - Raise `PromptLoadError` with all attempted sources and failure reasons if all fail
    - _Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [x] 2.6 Write property test for system prompt fallback chain priority
    - **Property 11: System prompt fallback chain priority**
    - Generate random combinations of available/failing prompt sources, verify highest-priority available source is used
    - **Validates: Requirements 7.2, 7.3, 7.4, 7.5, 7.6, 7.7**

  - [x] 2.7 Write property test for all prompt sources failure
    - **Property 12: All prompt sources failure**
    - Generate random failure reasons for all prompt sources, verify startup failure with all reasons listed in error message
    - **Validates: Requirements 7.8**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement deterministic labelers
  - [x] 4.1 Implement source detection (`labelers/source.py`)
    - Implement `detect_source(message: dict) -> str` function
    - Detect CloudWatch: presence of `AlarmName` + `NewStateValue`, or `source == "aws.cloudwatch"`
    - Detect SNS: `Type == "Notification"` + `TopicArn` present
    - Detect EventBridge: `source` + `detail-type` + `detail` fields in EventBridge schema
    - Return `"UNKNOWN"` if no pattern matches
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 4.2 Write property test for source label correctness
    - **Property 3: Source label correctness**
    - Use custom hypothesis strategies (`cloudwatch_message()`, `sns_message()`, `eventbridge_message()`, `unknown_message()`) to generate messages per source pattern, verify correct label assignment
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

  - [x] 4.3 Implement environment extraction (`labelers/environment.py`)
    - Implement `extract_environment(message: dict) -> str` function
    - Check for `environment`, `env`, or `environment_id` fields (including nested)
    - Extract AWS account ID from ARN fields (`TopicArn`, `Source`, `account` in EventBridge `detail`)
    - Scan text for "Environment: <value>" patterns in string values
    - Deep scan for env-related field names (`stage`, `namespace`, `cluster`, `stack`, `tier`) anywhere in message
    - Scan for known environment name patterns in env-hinted keys
    - Scan for any ARN string anywhere and extract account ID
    - Fall back to `"UNKNOWN"`
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 4.4 Write property test for environment label hierarchical extraction
    - **Property 6: Environment label hierarchical extraction**
    - Generate messages with/without env fields and ARNs, verify fallback chain precedence
    - **Validates: Requirements 5.1, 5.2, 5.3**

- [x] 5. Implement LLM integration and A2A forwarder
  - [x] 5.1 Implement LLM client (`llm.py`)
    - Implement `create_llm_client(config: AgentConfig)` function
    - Initialize `ChatOpenAI` (or equivalent) with provider, model, and API key from config
    - Validate configuration; raise descriptive error on invalid config
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 5.2 Implement A2A forwarder (`forwarder.py`)
    - Implement `build_a2a_task(enriched_message: dict) -> dict` to wrap message in A2A task envelope with JSON-RPC structure
    - Implement `forward_to_rca(enriched_message: dict, rca_url: str) -> bool` with retry logic
    - Retry up to 3 times with exponential backoff (1s, 2s, 4s) on error responses
    - Log errors on each failed attempt; log full enriched message on final failure
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 5.3 Write property test for retry on RCA agent failure
    - **Property 8: Retry on RCA agent failure**
    - Simulate RCA failures, verify exactly up to 3 retries before giving up
    - **Validates: Requirements 6.2**

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement graph nodes
  - [x] 7.1 Implement validate node (`nodes/validate.py`)
    - Implement `validate_node(state: TriageState) -> dict` that checks `raw_message` is a valid dict
    - Set `is_valid=True` on success, `is_valid=False` with descriptive `error` on failure
    - Implement `route_validation(state: TriageState) -> str` conditional edge function
    - _Requirements: 1.1, 1.2_

  - [x] 7.2 Write property test for valid JSON acceptance
    - **Property 1: Valid JSON acceptance**
    - Generate random valid JSON dicts, verify acceptance (no validation error)
    - **Validates: Requirements 1.1, 1.3**

  - [x] 7.3 Write property test for invalid JSON rejection
    - **Property 2: Invalid JSON rejection**
    - Generate random non-JSON strings, verify rejection with descriptive error and no labels produced
    - **Validates: Requirements 1.2**

  - [x] 7.4 Implement label_source node (`nodes/label_source.py`)
    - Implement `label_source_node(state: TriageState) -> dict` that calls `detect_source()` and updates `labels.source`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 7.5 Implement label_event_type node (`nodes/label_event_type.py`)
    - Implement `label_event_type_node(state: TriageState) -> dict` that invokes LLM with system prompt to classify event type
    - Validate LLM output is "alert" or "notification"; retry once on invalid output
    - _Requirements: 3.1, 3.2_

  - [x] 7.6 Write property test for event type label validity
    - **Property 4: Event type label validity**
    - Generate random messages, verify event_type is exactly "alert" or "notification"
    - **Validates: Requirements 3.1**

  - [x] 7.7 Implement label_priority node (`nodes/label_priority.py`)
    - Implement `label_priority_node(state: TriageState) -> dict` that invokes LLM with system prompt to assign priority
    - Validate LLM output is "P1", "P2", or "P3"; retry once on invalid output
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 7.8 Write property test for priority label validity
    - **Property 5: Priority label validity**
    - Generate random messages, verify priority is exactly "P1", "P2", or "P3"
    - **Validates: Requirements 4.1**

  - [x] 7.9 Implement label_environment node (`nodes/label_environment.py`)
    - Implement `label_environment_node(state: TriageState) -> dict` that calls `extract_environment()` and updates `labels.environment`
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 7.10 Implement forward_to_rca node (`nodes/forward_to_rca.py`)
    - Implement `forward_to_rca_node(state: TriageState) -> dict` that calls `forward_to_rca()` from forwarder module
    - Set `forwarded=True` on success, `forwarded=False` with `forward_error` on failure
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 8. Implement LangGraph workflow
  - [x] 8.1 Build triage graph (`graph.py`)
    - Implement `build_triage_graph(llm, system_prompt: str, rca_url: str)` function
    - Create `StateGraph(TriageState)` with all 6 nodes: validate, label_source, label_event_type, label_priority, label_environment, forward_to_rca
    - Set entry point to `validate` with conditional edges (valid → label_source, invalid → END)
    - Wire sequential edges: label_source → label_event_type → label_priority → label_environment → forward_to_rca → END
    - Integrate `KAgentCheckpointer` for session persistence when `KAGENT_URL` is set
    - Compile and return the graph with checkpointer
    - _Requirements: 1.1, 1.2, 2.1, 3.1, 4.1, 5.1, 6.1_

- [x] 9. Implement HTTP server
  - [x] 9.1 Implement FastAPI server (`server.py`)
    - Dual-mode server: KAgentApp (when `KAGENT_URL` set) or standalone FastAPI
    - Standalone: `POST /triage` endpoint with request logging (timestamp, source IP, body)
    - KAgent mode: `KAgentApp` with A2A protocol, streaming, and session persistence
    - Load configuration via `load_config()` at startup; fail fast on invalid config
    - Load system prompt via `load_system_prompt()` at startup; fail fast if all sources fail
    - Initialize LLM client and build triage graph with `KAgentCheckpointer` at startup
    - Serve `.well-known/agent-card.json` for A2A discovery
    - Return 400 for invalid JSON, 500 for processing errors, 200 with triage result on success
    - Configurable log level via `LOG_LEVEL` env var
    - _Requirements: 1.1, 1.2, 1.3, 7.1, 8.1, 8.2, 8.3, 9.1, 9.2_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Create Dockerfile and Kubernetes template
  - [x] 11.1 Create Dockerfile
    - Use `python:3.12-slim` base image
    - Create non-root `appuser` (UID 1000) for security
    - Copy `requirements.txt` and install dependencies
    - Copy application source code
    - Expose service port (default 8080)
    - Set entrypoint to run via `uvicorn`
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [x] 11.2 Create KAgent Kubernetes template (`k8s/kagent.yaml`)
    - Define kagent `Agent` CRD (apiVersion: kagent.dev/v1alpha2, kind: Agent, type: BYO)
    - Configure container image with env vars from Secrets (LLM_API_KEY) and inline (LLM_PROVIDER, LLM_MODEL, RCA_AGENT_URL)
    - Enable OpenTelemetry tracing via OTEL env vars
    - Create `.well-known/agent-card.json` for A2A protocol discovery
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use the `hypothesis` library with custom strategies for generating realistic alert messages
- Unit tests validate specific examples and edge cases
- The implementation language is Python, matching the design document
- The agent supports dual-mode operation: standalone FastAPI (local dev) and KAgentApp (kagent cluster)
- KAgentCheckpointer provides session persistence when running under kagent
- A2A agent card served at `.well-known/agent-card.json` for protocol discovery
- Dockerfile runs as non-root user (`appuser`) for security
- Kubernetes deployment uses kagent `Agent` CRD (BYO type) instead of raw Deployment/Service
