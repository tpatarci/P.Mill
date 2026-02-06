"""Report generation for Program Mill verification results."""

import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from backend.analysis.ast_parser import FunctionInfo, parse_python_file
from backend.models import VerificationIssue, VerificationReport


def generate_report(
    file_path: str,
    source_code: str,
    functions: List[FunctionInfo],
    issues: List[VerificationIssue],
    language: str = "python"
) -> VerificationReport:
    """
    Generate a verification report.

    Args:
        file_path: Path to the analyzed file
        source_code: Source code that was analyzed
        functions: List of functions found
        issues: List of issues found
        language: Programming language

    Returns:
        Complete VerificationReport
    """
    # Calculate code hash
    code_hash = hashlib.sha256(source_code.encode()).hexdigest()

    # Build report
    return VerificationReport(
        analysis_id=str(uuid.uuid4()),
        timestamp=datetime.now(),
        code_hash=code_hash,
        file_path=file_path,
        language=language,
        function_count=len(functions),
        functions_analyzed=[f.name for f in functions],
        issues=issues,
        proven_properties=_extract_proven_properties(issues),
        assumptions=_extract_assumptions(issues),
        limitations=_extract_limitations(),
        metrics=_calculate_metrics(source_code, functions, issues)
    )


def _extract_proven_properties(issues: List[VerificationIssue]) -> List[str]:
    """Extract properties that were formally verified."""
    properties = []

    # If no security issues found, code passes security checks
    security_issues = [i for i in issues if i.category == "security"]
    if not security_issues:
        properties.append("No critical security vulnerabilities detected (Tier 1 & 2)")

    # If no resource leaks found
    leak_issues = [i for i in issues if "resource leak" in i.title.lower() or "file" in i.title.lower()]
    if not leak_issues:
        properties.append("No resource leaks detected (open() without context manager)")

    # If no mutable defaults
    mutable_issues = [i for i in issues if "mutable" in i.title.lower()]
    if not mutable_issues:
        properties.append("No mutable default arguments")

    return properties


def _extract_assumptions(issues: List[VerificationIssue]) -> List[str]:
    """Extract assumptions made during analysis."""
    assumptions = [
        "Static analysis assumes code paths are representative of runtime behavior",
        "AST analysis is limited to the provided source file",
        "External dependencies and library calls are not analyzed",
        "LLM-assisted checks (Tier 3) depend on model accuracy",
        "Cross-validation assumes AST facts are ground truth",
    ]
    return assumptions


def _extract_limitations() -> List[str]:
    """Extract analysis limitations."""
    return [
        "Dynamic code execution (eval, exec) not analyzed",
        "Inter-procedural analysis limited to single file",
        "Type inference based on annotations, not runtime behavior",
        "LLM responses may contain false positives or negatives",
        "Star imports from external modules not tracked",
        "Decorator side effects not analyzed",
        "Property/setter/descriptor behavior not fully analyzed",
    ]


def _calculate_metrics(
    source_code: str,
    functions: List[FunctionInfo],
    issues: List[VerificationIssue]
) -> dict:
    """Calculate analysis metrics."""
    lines = source_code.splitlines()
    loc = len([l for l in lines if l.strip() and not l.strip().startswith("#")])

    return {
        "total_lines": len(lines),
        "lines_of_code": loc,
        "function_count": len(functions),
        "issue_count": len(issues),
        "critical_issues": len([i for i in issues if i.severity == "critical"]),
        "high_issues": len([i for i in issues if i.severity == "high"]),
        "medium_issues": len([i for i in issues if i.severity == "medium"]),
        "low_issues": len([i for i in issues if i.severity == "low"]),
        "info_issues": len([i for i in issues if i.severity == "info"]),
        "tier1_findings": len([i for i in issues if i.tier.value == "tier1_deterministic"]),
        "tier2_findings": len([i for i in issues if i.tier.value == "tier2_heuristic"]),
        "tier3_findings": len([i for i in issues if i.tier.value == "tier3_semantic"]),
    }


def format_report_text(report: VerificationReport) -> str:
    """
    Format a verification report as human-readable text.

    Args:
        report: The verification report to format

    Returns:
        Formatted text string
    """
    lines = [
        "=" * 70,
        "Program Mill Verification Report",
        "=" * 70,
        "",
        f"File: {report.file_path}",
        f"Analysis ID: {report.analysis_id}",
        f"Timestamp: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Language: {report.language}",
        f"Functions Analyzed: {report.function_count}",
        "",
        "-" * 70,
        "Summary",
        "-" * 70,
        "",
    ]

    # Add metrics
    metrics = report.metrics
    lines.extend([
        f"Total Issues: {metrics.get('issue_count', 0)}",
        f"  Critical: {metrics.get('critical_issues', 0)}",
        f"  High: {metrics.get('high_issues', 0)}",
        f"  Medium: {metrics.get('medium_issues', 0)}",
        f"  Low: {metrics.get('low_issues', 0)}",
        "",
    ])

    # Add issues by severity
    if report.issues:
        lines.extend([
            "-" * 70,
            "Issues Found",
            "-" * 70,
            "",
        ])

        # Group by severity
        by_severity = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "info": [],
        }
        for issue in report.issues:
            by_severity[issue.severity].append(issue)

        for severity in ["critical", "high", "medium", "low", "info"]:
            issues_by_sev = by_severity[severity]
            if issues_by_sev:
                lines.append(f"{severity.upper()} ({len(issues_by_sev)}):")
                for issue in issues_by_sev:
                    lines.append(f"  - {issue.title}")
                    lines.append(f"    Location: {issue.location}")
                    if issue.evidence:
                        lines.append(f"    Evidence: {issue.evidence[0]}")
                    lines.append("")
    else:
        lines.extend([
            "No issues found!",
            "",
        ])

    # Add proven properties
    if report.proven_properties:
        lines.extend([
            "-" * 70,
            "Verified Properties",
            "-" * 70,
            "",
        ])
        for prop in report.proven_properties:
            lines.append(f"  ✓ {prop}")
        lines.append("")

    # Add assumptions
    if report.assumptions:
        lines.extend([
            "-" * 70,
            "Assumptions",
            "-" * 70,
            "",
        ])
        for assumption in report.assumptions[:5]:  # Show first 5
            lines.append(f"  • {assumption}")
        if len(report.assumptions) > 5:
            lines.append(f"  • ... and {len(report.assumptions) - 5} more")
        lines.append("")

    # Add limitations
    if report.limitations:
        lines.extend([
            "-" * 70,
            "Limitations",
            "-" * 70,
            "",
        ])
        for limitation in report.limitations[:5]:  # Show first 5
            lines.append(f"  • {limitation}")
        if len(report.limitations) > 5:
            lines.append(f"  • ... and {len(report.limitations) - 5} more")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


def save_report_json(report: VerificationReport, output_path: str) -> None:
    """
    Save a verification report as JSON.

    Args:
        report: The verification report to save
        output_path: Path to save the JSON file
    """
    Path(output_path).write_text(report.model_dump_json(indent=2))


def load_report_json(report_path: str) -> VerificationReport:
    """
    Load a verification report from JSON.

    Args:
        report_path: Path to the JSON file

    Returns:
        VerificationReport object
    """
    return VerificationReport.model_validate_json(Path(report_path).read_text())
