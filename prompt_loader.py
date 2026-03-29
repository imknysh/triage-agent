"""System prompt loader with multi-source fallback chain.

Loads the system prompt from multiple sources in priority order:
1. HTTP URL (SYSTEM_PROMPT_URL env var)
2. File path / ConfigMap (SYSTEM_PROMPT_FILE env var)
3. Default local file (prompts/system_prompt.txt)
"""

import os

import httpx
from pathlib import Path


class PromptLoadError(Exception):
    """Raised when all prompt sources fail to load."""
    pass


def load_system_prompt() -> str:
    """Load system prompt using fallback chain: URL → file → default."""
    errors: list[str] = []

    # 1. Try HTTP URL
    url = os.getenv("SYSTEM_PROMPT_URL")
    if url:
        try:
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            errors.append(f"HTTP URL ({url}): {e}")

    # 2. Try file path (ConfigMap or custom file)
    file_path = os.getenv("SYSTEM_PROMPT_FILE")
    if file_path:
        try:
            return Path(file_path).read_text()
        except Exception as e:
            errors.append(f"File path ({file_path}): {e}")

    # 3. Try default local file
    default_path = Path("prompts/system_prompt.txt")
    try:
        return default_path.read_text()
    except Exception as e:
        errors.append(f"Default file ({default_path}): {e}")

    raise PromptLoadError(
        "Failed to load system prompt from all sources:\n"
        + "\n".join(f"  - {err}" for err in errors)
    )
