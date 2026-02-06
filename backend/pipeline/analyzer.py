"""Main pipeline orchestrator for Program Mill analysis."""

import asyncio
from pathlib import Path
from typing import List, Optional

import structlog

from backend.analysis.ast_parser import (
    FunctionInfo,
    get_function_ast_node,
    parse_python_file,
)
from backend.analysis.fact_extractor import extract_function_facts
from backend.analysis.pattern_checker import run_tier2_checks
from backend.config import settings
from backend.llm import LLMAdapter
from backend.llm.prompts import build_null_safety_prompt
from backend.llm.response_parser import parse_null_safety_response
from backend.models import FunctionFacts, VerificationIssue, VerificationReport
from backend.pipeline.cross_validator import cross_validate_null_safety
from backend.pipeline.report_generator import format_report_text, generate_report


logger = structlog.get_logger()

# Maximum lines of code for Tier 3 LLM checks (to avoid excessive token usage)
MAX_LOC_FOR_LLM_CHECKS = 200


async def analyze_python_file(
    file_path: str,
    llm_adapter: Optional[LLMAdapter] = None
) -> VerificationReport:
    """
    Run full verification pipeline on a Python file.

    Pipeline steps:
    1. Read file
    2. Parse AST + extract functions
    3. For each function:
        a. Extract facts (AST analysis)
        b. Run Tier 2 pattern checks
        c. Run Tier 3 LLM checks (if adapter available and LOC <= threshold)
        d. Cross-validate LLM findings against AST
    4. Aggregate all issues
    5. Generate report

    Args:
        file_path: Path to the Python file to analyze
        llm_adapter: Optional LLM adapter for Tier 3 checks

    Returns:
        Complete VerificationReport with all findings
    """
    logger.info("analysis_started", file_path=file_path)

    # Step 1: Read source
    source_code = Path(file_path).read_text()

    # Step 2: Parse AST and extract functions
    tree, functions = parse_python_file(source_code)

    logger.info(
        "ast_parsed",
        file_path=file_path,
        function_count=len(functions)
    )

    all_issues: List[VerificationIssue] = []

    # Step 3: Analyze each function
    for func_info in functions:
        logger.debug(
            "analyzing_function",
            function_name=func_info.name,
            line_start=func_info.line_start
        )

        # Get the AST node for this function
        func_node = get_function_ast_node(tree, func_info.name)
        if func_node is None:
            logger.warning(
                "function_ast_node_not_found",
                function_name=func_info.name
            )
            continue

        # Extract facts
        facts = extract_function_facts(func_node, source_code)

        # Run Tier 2 checks (deterministic pattern checks)
        tier2_issues = run_tier2_checks(facts)
        all_issues.extend(tier2_issues)

        logger.debug(
            "tier2_checks_complete",
            function_name=func_info.name,
            issues_found=len(tier2_issues)
        )

        # Run Tier 3 checks (LLM-assisted) if adapter available
        if llm_adapter and facts.loc <= MAX_LOC_FOR_LLM_CHECKS:
            try:
                tier3_issues = await run_null_safety_check(facts, llm_adapter)
                all_issues.extend(tier3_issues)

                logger.debug(
                    "tier3_checks_complete",
                    function_name=facts.function_name,
                    issues_found=len(tier3_issues)
                )
            except Exception as e:
                logger.warning(
                    "tier3_check_failed",
                    function_name=facts.function_name,
                    error=str(e)
                )
        elif llm_adapter:
            logger.info(
                "tier3_check_skipped",
                function_name=facts.function_name,
                reason="function_too_large",
                loc=facts.loc,
                threshold=MAX_LOC_FOR_LLM_CHECKS
            )

    # Step 4: Generate report
    report = generate_report(
        file_path=file_path,
        source_code=source_code,
        functions=functions,
        issues=all_issues
    )

    logger.info(
        "analysis_complete",
        file_path=file_path,
        total_issues=len(all_issues),
        critical_issues=len([i for i in all_issues if i.severity == "critical"]),
        analysis_id=report.analysis_id
    )

    return report


async def run_null_safety_check(
    facts: FunctionFacts,
    llm_adapter: LLMAdapter
) -> List[VerificationIssue]:
    """
    Run Tier 3 null safety check with LLM and cross-validation.

    Args:
        facts: Extracted function facts
        llm_adapter: LLM adapter to use for the check

    Returns:
        List of VerificationIssue objects (0 or 1)
    """
    # Build prompt
    prompt = build_null_safety_prompt(facts)

    # Get LLM response
    raw_response = await llm_adapter.complete(
        prompt,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature
    )

    # Parse response
    answer_type, unsafe_params = parse_null_safety_response(raw_response)

    # Cross-validate against AST facts
    confidence, validation_result = cross_validate_null_safety(
        answer_type,
        unsafe_params,
        facts
    )

    # If UNCLEAR or SAFE with confirmation, no issue
    if answer_type == "UNCLEAR":
        return []

    if answer_type == "SAFE" and validation_result == "confirmed":
        return []

    # Build issue if unsafe or contradicted
    if answer_type == "UNSAFE" and unsafe_params:
        return [
            VerificationIssue(
                issue_id=f"{facts.qualified_name}:null_safety",
                severity="high" if validation_result == "confirmed" else "medium",
                category="logic",
                title=f"Null safety issue: {', '.join(unsafe_params)}",
                description=(
                    f"Function {facts.function_name} may crash if passed None "
                    f"for parameters: {', '.join(unsafe_params)}. "
                    f"These parameters are used without None checks."
                ),
                location=f"{facts.function_name}:{facts.line_start}",
                tier="tier3_semantic",
                confidence=confidence,
                evidence=[
                    f"LLM analysis: {raw_response}",
                    f"Cross-validation: {validation_result}",
                ],
                llm_metadata={
                    "prompt_template": "null_safety",
                    "model_id": llm_adapter.__class__.__name__,
                    "attempts": 1,
                    "first_response_parseable": True,
                    "raw_response": raw_response,
                    "parsed_answer": f"{answer_type}: {unsafe_params}",
                    "cross_validation_result": validation_result,
                }
            )
        ]

    return []


def analyze_python_file_sync(
    file_path: str,
    llm_adapter: Optional[LLMAdapter] = None
) -> VerificationReport:
    """
    Synchronous wrapper for analyze_python_file.

    Args:
        file_path: Path to the Python file to analyze
        llm_adapter: Optional LLM adapter for Tier 3 checks

    Returns:
        Complete VerificationReport with all findings
    """
    return asyncio.run(analyze_python_file(file_path, llm_adapter))
