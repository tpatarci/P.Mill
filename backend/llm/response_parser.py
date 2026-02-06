"""Response parsing utilities for LLM outputs."""

import re
from typing import List, Tuple


def parse_null_safety_response(response: str) -> Tuple[str, List[str]]:
    """
    Parse LLM response for null safety check.

    The response should be in one of these formats:
    - "SAFE: all parameters handled"
    - "UNSAFE: param1, param2 (reason)"
    - "UNCLEAR"
    - Or any variation with extra text

    Args:
        response: Raw LLM response string

    Returns:
        A tuple of (answer_type, unsafe_params)
        - answer_type: "SAFE", "UNSAFE", or "UNCLEAR"
        - unsafe_params: list of parameter names (empty if SAFE)

    Examples:
        >>> parse_null_safety_response("UNSAFE: name (calls .upper())")
        ('UNSAFE', ['name'])

        >>> parse_null_safety_response("SAFE: all parameters handled")
        ('SAFE', [])

        >>> parse_null_safety_response("I'm not sure")
        ('UNCLEAR', [])
    """
    response = response.strip()

    # Check for UNSAFE first (must come before SAFE since UNSAFE contains SAFE)
    unsafe_match = re.search(r"UNSAFE\s*:?\s*(.+)", response, re.IGNORECASE)
    if unsafe_match:
        # Extract parameter names from the response
        # Parameters are typically at the start before parentheses
        details = unsafe_match.group(1)

        # Extract parameter names (alphanumeric + underscore)
        # Look for patterns like "name, data" or "name and data" or just "name"
        params = _extract_param_names(details)
        return "UNSAFE", params

    # Check for SAFE
    if re.search(r"SAFE", response, re.IGNORECASE):
        return "SAFE", []

    # Default to UNCLEAR for any other response
    return "UNCLEAR", []


def _extract_param_names(text: str) -> List[str]:
    """
    Extract parameter names from text.

    Looks for Python identifier names (alphanumeric + underscore)
    in the text. Returns the first few that look like parameters.

    Args:
        text: Text to search for parameter names

    Returns:
        List of parameter names found
    """
    # Find all Python identifiers
    identifiers = re.findall(r"\b[a-z_][a-z0-9_]*\b", text, re.IGNORECASE)

    # Filter out common words that are not parameter names
    exclude = {
        "the", "and", "or", "but", "for", "not", "all", "any", "can",
        "will", "would", "should", "could", "might", "must", "may",
        "calls", "check", "checks", "detected", " crash", "crashes",
        "because", "since", "as", "if", "when", "then", "than", "that",
        "this", "these", "those", "them", "they", "their", "there",
        "here", "where", "which", "each", "every", "some", "such", "same",
        "used", "use", "using", "without", "with", "from", "into", "to",
        "in", "on", "at", "by", "of", "is", "it", "its", "are", "was",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "no", "yes", "none", "null", "nil", "safe", "unsafe", "unclear",
        "parameters", "parameter", "params", "param", "function", "func",
        "handled", "handlers", "handling", "list", "dict", "set", "str",
        "int", "float", "bool", "true", "false", "return", "returns",
    }

    params = [id for id in identifiers if id.lower() not in exclude and len(id) > 1]

    # Return unique names, limited to reasonable count
    seen = set()
    unique_params = []
    for p in params:
        if p not in seen:
            seen.add(p)
            unique_params.append(p)
            if len(unique_params) >= 5:  # Limit to 5 params
                break

    return unique_params


def is_safe_response(response: str) -> bool:
    """Check if response indicates SAFE (no issues)."""
    answer_type, _ = parse_null_safety_response(response)
    return answer_type == "SAFE"


def is_unsafe_response(response: str) -> bool:
    """Check if response indicates UNSAFE (has issues)."""
    answer_type, _ = parse_null_safety_response(response)
    return answer_type == "UNSAFE"


def is_unclear_response(response: str) -> bool:
    """Check if response is UNCLEAR (could not determine)."""
    answer_type, _ = parse_null_safety_response(response)
    return answer_type == "UNCLEAR"
