"""Prompt templates for LLM-assisted verification checks."""

from backend.models import FunctionFacts


def _build_param_list(facts: FunctionFacts) -> str:
    """Build parameter list string for prompt."""
    if not facts.parameters:
        return "none"

    parts = []
    for param in facts.parameters:
        type_hint = param.type_hint or "no type hint"
        default = "has default" if param.has_default else "no default"
        parts.append(f"{param.name}: {type_hint}, {default}")

    return "; ".join(parts)


def _build_none_check_facts(facts: FunctionFacts) -> str:
    """Build None check facts string for prompt."""
    if not facts.has_none_checks:
        return "No None checks detected"

    return f"Has None checks for: {', '.join(facts.has_none_checks)}"


def _build_call_list(facts: FunctionFacts) -> str:
    """Build function call list for prompt."""
    if not facts.calls:
        return "none"

    # Show first 10 calls only
    calls = facts.calls[:10]
    result = ", ".join(calls)
    if len(facts.calls) > 10:
        result += f" (and {len(facts.calls) - 10} more)"
    return result


NULL_SAFETY_PROMPT = """You are checking Python functions for null safety issues.

EXAMPLES:
---
Function: def greet(name): return f"Hello, {{name.upper()}}"
Facts: Parameters=[name: no type hint, no default]. No None checks in body. Calls: str.upper()
Question: Which parameters crash if None?
Answer: UNSAFE: name (calls .upper() on it without None check)
---
Function: def safe_greet(name):
    if name is None: return "Hello, stranger"
    return f"Hello, {{name.upper()}}"
Facts: Parameters=[name: no type hint, no default]. Has None check for 'name'.
Question: Which parameters crash if None?
Answer: SAFE: all parameters handled
---
Function: def process(data, items):
    if data is None: data = []
    return data + items
Facts: Parameters=[data: no type hint, no default; items: no type hint, no default]. Has None check for 'data'. Calls: list addition
Question: Which parameters crash if None?
Answer: UNSAFE: items (used in addition without None check)
---

NOW ANALYZE:
Function:
```python
{function_code}
```
Facts: Parameters=[{param_list}]. {none_check_facts}. Calls: {call_list}
Question: Which parameters crash if passed None?
Answer:"""


def build_null_safety_prompt(facts: FunctionFacts) -> str:
    """
    Build a prompt for null safety analysis.

    The prompt asks the LLM to identify which parameters would cause
    a crash (AttributeError, TypeError, etc.) if passed None.

    Args:
        facts: Extracted function facts

    Returns:
        The formatted prompt string
    """
    return NULL_SAFETY_PROMPT.format(
        function_code=facts.source_code,
        param_list=_build_param_list(facts),
        none_check_facts=_build_none_check_facts(facts),
        call_list=_build_call_list(facts),
    )


# Additional prompt templates can be added here for future checks
# Examples: type consistency, unused parameters, etc.
