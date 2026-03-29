"""Environment extraction labeler for alert messages.

Hierarchical extraction with fallback chain:
1. Explicit environment/env/environment_id fields (including nested)
2. AWS account ID from ARN fields (TopicArn, Source, account in EventBridge detail)
3. Deep scan: known env-related field names and known env name patterns anywhere in the message
4. ARN scan: find any ARN string anywhere in the message and extract account ID
5. Fall back to "UNKNOWN"
"""

import re

# Field names to check for explicit environment values
_ENV_FIELD_NAMES = ("environment", "env", "environment_id")

# Broader set of field names that may contain environment info (for deep scan)
_ENV_HINT_FIELDS = (
    "environment", "env", "environment_id", "env_name", "env_id",
    "stage", "deployment_environment", "deploy_env", "target_env",
    "namespace", "cluster", "stack", "tier",
)

# Known environment name patterns (for fullmatch on stripped values)
_KNOWN_ENV_NAMES = re.compile(
    r"(production|prod|staging|stage|development|dev|qa|uat|"
    r"sandbox|test|testing|preprod|pre-prod|demo|perf|load-test)",
    re.IGNORECASE,
)

# Pattern to extract environment name after keywords like "Environment:", "Env:", etc.
_ENV_TEXT_PATTERN = re.compile(
    r"(?:environment|env|env_name|stage|namespace)\s*[:=]\s*(\S+)",
    re.IGNORECASE,
)

_ARN_PATTERN = re.compile(r"arn:[^:]+:[^:]+:[^:]*:(\d{12}):")


def _scan_text_for_env_keyword(obj, depth: int = 0) -> str | None:
    """Scan string values for 'Environment: <value>' patterns."""
    if depth > 5:
        return None

    if isinstance(obj, str):
        match = _ENV_TEXT_PATTERN.search(obj)
        if match:
            return match.group(1).strip()

    elif isinstance(obj, dict):
        for value in obj.values():
            result = _scan_text_for_env_keyword(value, depth + 1)
            if result:
                return result

    elif isinstance(obj, list):
        for item in obj:
            result = _scan_text_for_env_keyword(item, depth + 1)
            if result:
                return result

    return None


def _extract_account_from_arn(arn: str) -> str | None:
    """Extract AWS account ID from an ARN string."""
    if not isinstance(arn, str) or not arn.startswith("arn:"):
        return None
    parts = arn.split(":")
    if len(parts) >= 5 and parts[4]:
        return parts[4]
    return None


def _find_env_field(obj: dict) -> str | None:
    """Search for an explicit environment field in a dictionary."""
    for field in _ENV_FIELD_NAMES:
        value = obj.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_account_id(message: dict, detail: dict | None) -> str | None:
    """Extract AWS account ID from known ARN fields or EventBridge detail."""
    account = _extract_account_from_arn(message.get("TopicArn", ""))
    if account:
        return account

    account = _extract_account_from_arn(message.get("Source", ""))
    if account:
        return account

    if isinstance(detail, dict):
        detail_account = detail.get("account")
        if isinstance(detail_account, str) and detail_account.strip():
            return detail_account.strip()

    return None


def _deep_scan_env(obj, depth: int = 0) -> str | None:
    """Recursively scan a dict/list for environment hints.

    Checks env-related field names and known environment name patterns
    in string values, up to 5 levels deep.
    """
    if depth > 5:
        return None

    if isinstance(obj, dict):
        # Check env hint fields at this level
        for field in _ENV_HINT_FIELDS:
            value = obj.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()

        # Recurse into nested dicts/lists
        for value in obj.values():
            result = _deep_scan_env(value, depth + 1)
            if result:
                return result

    elif isinstance(obj, list):
        for item in obj:
            result = _deep_scan_env(item, depth + 1)
            if result:
                return result

    return None


def _scan_for_known_env_name(obj, depth: int = 0) -> str | None:
    """Scan dict values for known environment name patterns.

    Only matches when a dict key looks environment-related (contains 'env',
    'stage', 'tier', 'namespace', 'cluster', 'stack', 'deploy') and the
    value is a known env name.
    """
    if depth > 5:
        return None

    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = key.lower() if isinstance(key, str) else ""
            # Only check values of keys that hint at environment
            if isinstance(value, str) and any(
                hint in key_lower
                for hint in ("env", "stage", "tier", "namespace", "cluster", "stack", "deploy")
            ):
                stripped = value.strip().lower()
                if _KNOWN_ENV_NAMES.fullmatch(stripped):
                    return stripped

            # Recurse into nested structures
            result = _scan_for_known_env_name(value, depth + 1)
            if result:
                return result

    elif isinstance(obj, list):
        for item in obj:
            result = _scan_for_known_env_name(item, depth + 1)
            if result:
                return result

    return None


def _scan_for_arn_account(obj, depth: int = 0) -> str | None:
    """Scan all string values for any ARN and extract the account ID."""
    if depth > 5:
        return None

    if isinstance(obj, str):
        match = _ARN_PATTERN.search(obj)
        if match:
            return match.group(1)

    elif isinstance(obj, dict):
        for value in obj.values():
            result = _scan_for_arn_account(value, depth + 1)
            if result:
                return result

    elif isinstance(obj, list):
        for item in obj:
            result = _scan_for_arn_account(item, depth + 1)
            if result:
                return result

    return None


def extract_environment(message: dict) -> str:
    """Extract environment information from an alert message.

    Follows a hierarchical fallback chain:
    1. Explicit environment/env/environment_id fields at top level and in 'detail'
    2. AWS account ID from known ARN fields (TopicArn, Source, detail.account)
    3. Deep scan for env-related field names anywhere in the message
    4. Scan for known environment name patterns in any string value
    5. Scan for any ARN string anywhere and extract account ID
    6. Fall back to "UNKNOWN"
    """
    # Step 1: Explicit env fields at top level
    env = _find_env_field(message)
    if env:
        return env

    # Step 1b: Explicit env fields in 'detail'
    detail = message.get("detail")
    if isinstance(detail, dict):
        env = _find_env_field(detail)
        if env:
            return env

    # Step 2: Known ARN fields
    account = _extract_account_id(message, detail if isinstance(detail, dict) else None)
    if account:
        return account

    # Step 3: Scan text for "Environment: <value>" patterns in string values
    env = _scan_text_for_env_keyword(message)
    if env:
        return env

    # Step 4: Deep scan for env hint fields anywhere in the message
    env = _deep_scan_env(message)
    if env:
        return env

    # Step 5: Scan for known environment name patterns in string values
    env = _scan_for_known_env_name(message)
    if env:
        return env

    # Step 6: Scan for any ARN anywhere and extract account ID
    account = _scan_for_arn_account(message)
    if account:
        return account

    return "UNKNOWN"
