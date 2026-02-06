"""Cross-validation of LLM results against AST facts.

This module implements rules to validate LLM claims by comparing them
against deterministic AST facts. When LLM and AST agree, confidence is HIGH.
When they contradict, confidence is LOW.
"""

from typing import List, Tuple

from backend.models import FindingConfidence, FunctionFacts


def cross_validate_null_safety(
    llm_answer: str,
    unsafe_params: List[str],
    facts: FunctionFacts
) -> Tuple[FindingConfidence, str]:
    """
    Cross-validate LLM null safety claim against AST facts.

    Validation Rules:
    1. UNCLEAR → no_data (LLM couldn't determine, nothing to validate)
    2. SAFE + all params have None checks → confirmed (AST supports LLM)
    3. SAFE + some params lack None checks → contradicted (LLM missed issues)
    4. UNSAFE + unsafe params lack None checks → confirmed (AST supports LLM)
    5. UNSAFE + unsafe params have None checks → contradicted (LLM false positive)

    Args:
        llm_answer: The parsed LLM response ("SAFE", "UNSAFE", or "UNCLEAR")
        unsafe_params: List of parameters LLM identified as unsafe
        facts: AST facts for the function

    Returns:
        A tuple of (confidence, validation_result)
        - confidence: HIGH, MEDIUM, LOW, or INCONCLUSIVE
        - validation_result: "confirmed", "no_data", or "contradicted"

    Examples:
        >>> facts = FunctionFacts(has_none_checks=["name"], parameters=[...])
        >>> cross_validate_null_safety("SAFE", [], facts)
        (FindingConfidence.HIGH, 'confirmed')

        >>> facts = FunctionFacts(has_none_checks=[], parameters=[...])
        >>> cross_validate_null_safety("UNSAFE", ["name"], facts)
        (FindingConfidence.HIGH, 'confirmed')
    """
    # Rule 1: UNCLEAR → no data
    if llm_answer == "UNCLEAR":
        return FindingConfidence.INCONCLUSIVE, "no_data"

    # Get parameter names from facts
    param_names = [p.name for p in facts.parameters]

    # Rule 2: SAFE + all params have None checks → confirmed
    if llm_answer == "SAFE":
        # Check if AST confirms all params have None checks
        checked_params = set(facts.has_none_checks)
        all_params_checked = all(p in checked_params for p in param_names)

        if all_params_checked:
            return FindingConfidence.HIGH, "confirmed"
        else:
            # LLM says SAFE but AST says some params lack None checks
            return FindingConfidence.LOW, "contradicted"

    # Rule 3: UNSAFE + unsafe params lack None checks → confirmed
    if llm_answer == "UNSAFE":
        # Check each unsafe param
        for param_name in unsafe_params:
            if param_name in facts.has_none_checks:
                # LLM says unsafe but AST shows None check exists
                return FindingConfidence.LOW, "contradicted"

        # All unsafe params indeed lack None checks
        return FindingConfidence.HIGH, "confirmed"

    # Should not reach here
    return FindingConfidence.INCONCLUSIVE, "no_data"


def cross_validate_has_return_on_all_paths(
    llm_answer: str,
    facts: FunctionFacts
) -> Tuple[FindingConfidence, str]:
    """
    Cross-validate LLM claim about return paths against AST facts.

    Args:
        llm_answer: LLM response about return coverage
        facts: AST facts for the function

    Returns:
        A tuple of (confidence, validation_result)
    """
    if llm_answer == "UNCLEAR":
        return FindingConfidence.INCONCLUSIVE, "no_data"

    if llm_answer == "SAFE" and facts.has_return_on_all_paths:
        return FindingConfidence.HIGH, "confirmed"

    if llm_answer == "UNSAFE" and not facts.has_return_on_all_paths:
        return FindingConfidence.HIGH, "confirmed"

    return FindingConfidence.LOW, "contradicted"


def cross_validate_exception_handling(
    llm_answer: str,
    facts: FunctionFacts
) -> Tuple[FindingConfidence, str]:
    """
    Cross-validate LLM claim about exception handling against AST facts.

    Args:
        llm_answer: LLM response about exception handling
        facts: AST facts for the function

    Returns:
        A tuple of (confidence, validation_result)
    """
    if llm_answer == "UNCLEAR":
        return FindingConfidence.INCONCLUSIVE, "no_data"

    # If LLM says bare except is a problem
    if "bare except" in llm_answer.lower() and facts.has_bare_except:
        return FindingConfidence.HIGH, "confirmed"

    if "bare except" in llm_answer.lower() and not facts.has_bare_except:
        return FindingConfidence.LOW, "contradicted"

    # If LLM says broad exception handling is a problem
    if "broad" in llm_answer.lower() and facts.has_broad_except:
        return FindingConfidence.HIGH, "confirmed"

    if "broad" in llm_answer.lower() and not facts.has_broad_except:
        return FindingConfidence.LOW, "contradicted"

    return FindingConfidence.MEDIUM, "no_data"
