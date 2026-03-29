"""Configuration module for the Alert Triage Agent.

Reads and validates all configuration from environment variables.
Supported LLM providers: openai, azure, anthropic.
"""

import os
from typing import Optional

from pydantic import BaseModel, Field, model_validator

SUPPORTED_LLM_PROVIDERS = {"openai", "azure", "anthropic"}


class AgentConfig(BaseModel):
    """Agent configuration loaded from environment variables."""

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    rca_agent_url: str = "http://localhost:9090"
    service_port: int = Field(default=8080, ge=1, le=65535)
    system_prompt_url: Optional[str] = None
    system_prompt_file: Optional[str] = None

    @model_validator(mode="after")
    def validate_llm_config(self) -> "AgentConfig":
        if self.llm_provider not in SUPPORTED_LLM_PROVIDERS:
            raise ValueError(
                f"Unsupported LLM provider: '{self.llm_provider}'. "
                f"Supported providers: {', '.join(sorted(SUPPORTED_LLM_PROVIDERS))}"
            )
        if not self.llm_model or not self.llm_model.strip():
            raise ValueError("LLM model name must not be empty.")
        return self


def load_config() -> AgentConfig:
    """Load agent configuration from environment variables.

    Reads:
        LLM_PROVIDER (default: "openai")
        LLM_MODEL (default: "gpt-4o-mini")
        LLM_API_KEY (default: "")
        RCA_AGENT_URL (default: "http://localhost:9090")
        SERVICE_PORT (default: 8080)
        SYSTEM_PROMPT_URL (optional)
        SYSTEM_PROMPT_FILE (optional)

    Raises:
        ValueError: If LLM configuration is invalid.
    """
    rca_agent_url = os.getenv("RCA_AGENT_URL", "").strip()

    kwargs: dict = {}
    if rca_agent_url:
        kwargs["rca_agent_url"] = rca_agent_url

    llm_provider = os.getenv("LLM_PROVIDER")
    if llm_provider is not None:
        kwargs["llm_provider"] = llm_provider

    llm_model = os.getenv("LLM_MODEL")
    if llm_model is not None:
        kwargs["llm_model"] = llm_model

    llm_api_key = os.getenv("LLM_API_KEY")
    if llm_api_key is not None:
        kwargs["llm_api_key"] = llm_api_key

    service_port = os.getenv("SERVICE_PORT")
    if service_port is not None:
        kwargs["service_port"] = int(service_port)

    system_prompt_url = os.getenv("SYSTEM_PROMPT_URL")
    if system_prompt_url is not None:
        kwargs["system_prompt_url"] = system_prompt_url

    system_prompt_file = os.getenv("SYSTEM_PROMPT_FILE")
    if system_prompt_file is not None:
        kwargs["system_prompt_file"] = system_prompt_file

    return AgentConfig(**kwargs)
