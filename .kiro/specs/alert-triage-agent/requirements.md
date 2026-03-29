# Requirements Document

## Introduction

The Alert Triage Agent is an AI-powered agent built with the LangGraph framework. It receives alerts and notifications in JSON format from multiple sources (CloudWatch, SNS, EventBridge), analyzes and labels them with source, event type, priority, and environment information, then forwards the enriched messages to a downstream Root Cause Analysis (RCA) agent using A2A protocol. The agent is containerized and deployable to Kubernetes via a KAgent template.

## Glossary

- **Alert_Triage_Agent**: The LangGraph-based AI agent that receives, labels, and forwards alert messages
- **RCA_Agent**: An external Root Cause Analysis agent that receives enriched alert messages for further investigation
- **Alert_Message**: A JSON-formatted event or notification received from a source system
- **Label**: A key-value metadata annotation added to an Alert_Message during triage
- **Source_Label**: A label identifying the origin system of an Alert_Message (e.g., CW, SNS, EventBridge)
- **Event_Type_Label**: A label classifying the Alert_Message as either "alert" or "notification"
- **Priority_Label**: A label indicating urgency level (P1, P2, or P3) determined by LLM analysis
- **Environment_Label**: A label identifying the environment name or ID extracted from the Alert_Message, falling back to the AWS account ID
- **System_Prompt**: A predefined instruction set that configures the LLM behavior for alert triage
- **Prompt_Source**: A location from which the System_Prompt can be loaded — either a remote HTTP URL, a file path (including Kubernetes ConfigMap-mounted files), or the default local file
- **KAgent_Template**: A Kubernetes manifest template used to deploy the Alert_Triage_Agent to a Kubernetes cluster

## Requirements

### Requirement 1: Ingest Alert Messages

**User Story:** As an operations engineer, I want the agent to accept JSON-formatted alert messages from multiple sources, so that I have a single entry point for triage.

#### Acceptance Criteria

1. WHEN an Alert_Message is received in valid JSON format, THE Alert_Triage_Agent SHALL accept the message for processing
2. IF an Alert_Message is received in invalid JSON format, THEN THE Alert_Triage_Agent SHALL reject the message and return a descriptive error response
3. THE Alert_Triage_Agent SHALL accept Alert_Messages originating from CloudWatch, SNS, and EventBridge

### Requirement 2: Label Source Name

**User Story:** As an operations engineer, I want each alert labeled with its source system, so that I can identify where the alert originated.

#### Acceptance Criteria

1. WHEN an Alert_Message originates from CloudWatch, THE Alert_Triage_Agent SHALL add a Source_Label with value "CW"
2. WHEN an Alert_Message originates from SNS, THE Alert_Triage_Agent SHALL add a Source_Label with value "SNS"
3. WHEN an Alert_Message originates from AWS EventBridge, THE Alert_Triage_Agent SHALL add a Source_Label with value "EventBridge"
4. IF the source of an Alert_Message cannot be determined, THEN THE Alert_Triage_Agent SHALL add a Source_Label with value "UNKNOWN"

### Requirement 3: Label Event Type

**User Story:** As an operations engineer, I want each alert labeled with its event type, so that I can distinguish alerts from notifications.

#### Acceptance Criteria

1. WHEN an Alert_Message is processed, THE Alert_Triage_Agent SHALL add an Event_Type_Label with value "alert" or "notification"
2. THE Alert_Triage_Agent SHALL classify the Event_Type_Label based on the content and structure of the Alert_Message

### Requirement 4: Label Priority

**User Story:** As an operations engineer, I want each alert assigned a priority level, so that I can focus on the most critical issues first.

#### Acceptance Criteria

1. WHEN an Alert_Message is processed, THE Alert_Triage_Agent SHALL analyze the message content using the configured LLM and assign a Priority_Label of "P1", "P2", or "P3"
2. THE Alert_Triage_Agent SHALL assign "P1" to Alert_Messages indicating service outages or critical failures
3. THE Alert_Triage_Agent SHALL assign "P2" to Alert_Messages indicating degraded performance or warnings
4. THE Alert_Triage_Agent SHALL assign "P3" to Alert_Messages indicating informational or low-impact events

### Requirement 5: Label Environment

**User Story:** As an operations engineer, I want each alert labeled with the environment it came from, so that I can scope the impact of an issue.

#### Acceptance Criteria

1. WHEN an Alert_Message contains an environment name or environment ID, THE Alert_Triage_Agent SHALL add an Environment_Label with that value
2. WHEN an Alert_Message does not contain an environment name or environment ID, THE Alert_Triage_Agent SHALL extract the AWS account ID from the message and use it as the Environment_Label
3. IF neither an environment identifier nor an AWS account ID can be determined, THEN THE Alert_Triage_Agent SHALL add an Environment_Label with value "UNKNOWN"

### Requirement 6: Forward Enriched Message to RCA Agent

**User Story:** As an operations engineer, I want the enriched alert forwarded to the RCA agent using A2A protocol, so that root cause analysis can begin automatically.

#### Acceptance Criteria

1. WHEN all labels have been added to an Alert_Message, THE Alert_Triage_Agent SHALL send the enriched Alert_Message to the RCA_Agent via A2A protocol to the configured RCA agent URL
2. IF the RCA_Agent returns an error response, THEN THE Alert_Triage_Agent SHALL log the error and retry the request up to 3 times
3. IF all retry attempts to the RCA_Agent fail, THEN THE Alert_Triage_Agent SHALL log the failure with the enriched Alert_Message for manual review

### Requirement 7: System Prompt Configuration

**User Story:** As a developer, I want a well-defined system prompt for the agent that can be loaded from multiple sources, so that the LLM produces consistent and accurate triage results and the prompt can be managed externally in production environments.

#### Acceptance Criteria

1. THE Alert_Triage_Agent SHALL use a System_Prompt that instructs the LLM to analyze alert messages and determine event type and priority
2. THE Alert_Triage_Agent SHALL support loading the System_Prompt from a remote HTTP URL when the `SYSTEM_PROMPT_URL` environment variable is configured
3. THE Alert_Triage_Agent SHALL support loading the System_Prompt from a file path (including Kubernetes ConfigMap-mounted files) when the `SYSTEM_PROMPT_FILE` environment variable is configured
4. THE Alert_Triage_Agent SHALL fall back to loading the System_Prompt from the default local file (`prompts/system_prompt.txt`) when no other source is configured
5. THE Alert_Triage_Agent SHALL apply the following priority order when multiple prompt sources are configured: HTTP URL (highest) → file path / ConfigMap → default local file (lowest)
6. IF the configured HTTP URL prompt source fails to load (network error, non-200 response), THEN THE Alert_Triage_Agent SHALL fall through to the next source in the priority chain
7. IF the configured file path prompt source fails to load (file not found, permission error), THEN THE Alert_Triage_Agent SHALL fall through to the next source in the priority chain
8. IF all configured prompt sources fail to load, THEN THE Alert_Triage_Agent SHALL fail to start and log a descriptive error message indicating which sources were attempted and why each failed

### Requirement 8: LLM Configuration

**User Story:** As a developer, I want the LLM to be configurable, so that I can switch models or providers without code changes.

#### Acceptance Criteria

1. THE Alert_Triage_Agent SHALL support configuring the LLM provider and model name via environment variables or a configuration file
2. WHEN no LLM configuration is provided, THE Alert_Triage_Agent SHALL use a default LLM configuration
3. IF an invalid LLM configuration is provided, THEN THE Alert_Triage_Agent SHALL fail to start and log a descriptive error message

### Requirement 9: RCA Agent URL Configuration

**User Story:** As a developer, I want the RCA agent URL to be configurable, so that I can point to different RCA agent instances per environment.

#### Acceptance Criteria

1. THE Alert_Triage_Agent SHALL read the RCA_Agent URL from an environment variable or configuration file
2. IF no RCA_Agent URL is configured, THEN THE Alert_Triage_Agent SHALL fail to start and log a descriptive error message

### Requirement 10: Dockerfile

**User Story:** As a DevOps engineer, I want a Dockerfile for the agent, so that I can build a container image for deployment.

#### Acceptance Criteria

1. THE Dockerfile SHALL build a container image that runs the Alert_Triage_Agent
2. THE Dockerfile SHALL use a minimal base image appropriate for Python applications
3. THE Dockerfile SHALL install all required dependencies from a requirements or lock file
4. THE Dockerfile SHALL expose the agent's service port

### Requirement 11: KAgent Kubernetes Template

**User Story:** As a DevOps engineer, I want a KAgent template, so that I can deploy the agent to a Kubernetes cluster.

#### Acceptance Criteria

1. THE KAgent_Template SHALL define a Kubernetes Deployment resource for the Alert_Triage_Agent
2. THE KAgent_Template SHALL define a Kubernetes Service resource to expose the Alert_Triage_Agent
3. THE KAgent_Template SHALL support injecting configuration values (LLM settings, RCA_Agent URL) via environment variables or ConfigMaps
4. THE KAgent_Template SHALL include resource requests and limits for the container
