"""LLM client initialization for the Alert Triage Agent.

Creates and configures a LangChain chat model based on the agent configuration.
Supported providers: openai, azure, anthropic.
"""

from langchain_openai import ChatOpenAI

from config import AgentConfig, SUPPORTED_LLM_PROVIDERS


def create_llm_client(config: AgentConfig) -> ChatOpenAI:
    """Create a LangChain chat model from the agent configuration.

    Args:
        config: An AgentConfig instance with llm_provider, llm_model, and llm_api_key.

    Returns:
        A configured ChatOpenAI (or compatible) instance.

    Raises:
        ValueError: If the provider is unsupported or the model name is empty.
    """
    if config.llm_provider not in SUPPORTED_LLM_PROVIDERS:
        raise ValueError(
            f"Unsupported LLM provider: '{config.llm_provider}'. "
            f"Supported providers: {', '.join(sorted(SUPPORTED_LLM_PROVIDERS))}"
        )

    if not config.llm_model or not config.llm_model.strip():
        raise ValueError("LLM model name must not be empty.")

    # All supported providers currently use ChatOpenAI as the LangChain interface.
    # Azure and anthropic are placeholders that can be swapped to dedicated classes later.
    return ChatOpenAI(
        model=config.llm_model,
        api_key=config.llm_api_key,
    )
