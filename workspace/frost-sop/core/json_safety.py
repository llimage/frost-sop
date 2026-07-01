"""
Safe JSON parsing utility for LLM responses.

Prevents JSON injection attacks (DoS, recursive structures, number overflow)
per OWASP ASVS 4.0 L1 §5.3.1 — Deserialization Attack Prevention.

Audit: S-001 fix (2026-07-01)
"""

import json
from typing import Any

# Maximum allowed JSON string length (prevents memory exhaustion via massive payloads)
MAX_JSON_LENGTH = 100_000  # 100 KB
# Maximum nesting depth (prevents recursive structures)
MAX_JSON_DEPTH = 10
# Safe numeric bounds (prevents float overflow attacks)
SAFE_FLOAT_MIN = -1e100
SAFE_FLOAT_MAX = 1e100
SAFE_INT_MIN = -(2**53)
SAFE_INT_MAX = 2**53


def _safe_float(x: str) -> float:
    """Clamp floats to safe range."""
    val = float(x)
    if val != val:  # NaN
        return 0.0
    return max(min(val, SAFE_FLOAT_MAX), SAFE_FLOAT_MIN)


def _safe_int(x: str) -> int:
    """Clamp ints to JS-safe range."""
    return max(min(int(x), SAFE_INT_MAX), SAFE_INT_MIN)


def _safe_constant(x: str) -> None:
    """Reject NaN, Infinity, -Infinity."""
    raise ValueError(f"Unsafe JSON constant: {x}")


def _get_depth(obj: Any, current: int = 0) -> int:
    """Recursively determine max nesting depth."""
    if isinstance(obj, dict):
        if not obj:
            return current
        return max(_get_depth(v, current + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return current
        return max(_get_depth(v, current + 1) for v in obj)
    return current


def safe_json_parse(
    json_str: str,
    max_length: int = MAX_JSON_LENGTH,
    max_depth: int = MAX_JSON_DEPTH,
) -> tuple[dict | None, str | None]:
    """
    Parse JSON safely with DoS protection.

    Returns (parsed_dict, error_message). On success, error_message is None.
    On failure, parsed_dict is None and error_message explains why.

    Protections:
    - Rejects payloads larger than max_length (memory DoS)
    - Rejects NaN, Infinity, -Infinity (number attacks)
    - Clamps floats/ints to safe ranges
    - Rejects deeply nested structures (recursion DoS)
    - Ensures result is a dict (not array/string/number)
    """
    if not json_str or not json_str.strip():
        return None, "Empty JSON string"

    if len(json_str) > max_length:
        return None, f"JSON response too large ({len(json_str)} bytes, max {max_length})"

    try:
        data = json.loads(
            json_str,
            parse_float=_safe_float,
            parse_int=_safe_int,
            parse_constant=_safe_constant,
        )
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    except ValueError as e:
        return None, f"Unsafe JSON value: {e}"

    # Depth check
    depth = _get_depth(data)
    if depth > max_depth:
        return None, f"JSON nesting depth {depth} exceeds limit {max_depth}"

    # Enforce dict result (most LLM responses should be JSON objects)
    if not isinstance(data, dict):
        return None, f"Expected JSON object, got {type(data).__name__}"

    return data, None


def safe_json_parse_or_default(
    json_str: str,
    default: dict,
    max_length: int = MAX_JSON_LENGTH,
    max_depth: int = MAX_JSON_DEPTH,
) -> dict:
    """
    Parse JSON safely, falling back to default on any failure.

    Convenience wrapper for LLM response parsing where a fallback config exists.
    """
    result, error = safe_json_parse(json_str, max_length, max_depth)
    if error is not None:
        return default
    assert result is not None, "safe_json_parse: no error but result is None"
    return result
