"""Report generation and export in multiple formats.

This module provides:
- JSON report export
- SARIF format export
- Console report formatting
- HTML report generation
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from backend.analysis.unified_analyzer import AnalysisResult

logger = structlog.get_logger()


class ReportExporter:
    """Export analysis reports in various formats."""

    def __init__(self, result: AnalysisResult) -> None:
        self.result = result

    def to_json(self, indent: int = 2) -> str:
        """
        Export report as JSON.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string
        """
        report = self._build_report_dict()

        # Convert datetime to string for JSON serialization
        def json_serializer(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        return json.dumps(report, indent=indent, default=json_serializer)

    def to_sarif(self) -> Dict[str, Any]:
        """
        Export report in SARIF format (Static Analysis Results Interchange Format).

        Returns:
            SARIF dict
        """
        # Build SARIF report
        sarif = {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "P.Mill",
                            "version": "1.0.0",
                            "informationUri": "https://github.com/tpatarci/P.Mill",
                            "rules": [],
                        }
                    },
                    "results": self._build_sarif_results(),
                    "invocations": [
                        {
                            "startTimeUtc": self.result.timestamp.isoformat(),
                            "endTimeUtc": datetime.now().isoformat(),
                        }
                    ],
                }
            ],
        }

        return sarif

    def _build_sarif_results(self) -> List[Dict[str, Any]]:
        """Build SARIF results from analysis issues."""
        results = []

        # Add logic issues
        for issue in self.result.logic_issues:
            results.append({
                "ruleId": f"logic.{issue['type']}",
                "level": self._map_severity_to_level(issue.get("severity", "low")),
                "message": {
                    "text": issue.get("description", ""),
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": self.result.file_path,
                            },
                            "region": {
                                "startLine": issue.get("line", 1),
                            },
                        },
                    }
                ],
            })

        # Add security issues
        for issue in self.result.security_issues:
            results.append({
                "ruleId": f"security.{issue['type']}",
                "level": self._map_severity_to_level(issue.get("severity", "medium")),
                "message": {
                    "text": issue.get("description", ""),
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": self.result.file_path,
                            },
                            "region": {
                                "startLine": issue.get("line", 1),
                            },
                        },
                    }
                ],
            })

        # Add performance issues
        for issue in self.result.performance_issues:
            results.append({
                "ruleId": f"performance.{issue['type']}",
                "level": self._map_severity_to_level(issue.get("severity", "low")),
                "message": {
                    "text": issue.get("description", ""),
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": self.result.file_path,
                            },
                            "region": {
                                "startLine": issue.get("line", 1),
                            },
                        },
                    }
                ],
            })

        # Add maintainability issues
        for issue in self.result.maintainability_issues:
            results.append({
                "ruleId": f"maintainability.{issue['type']}",
                "level": self._map_severity_to_level(issue.get("severity", "low")),
                "message": {
                    "text": issue.get("description", ""),
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": self.result.file_path,
                            },
                            "region": {
                                "startLine": issue.get("line", 1),
                            },
                        },
                    }
                ],
            })

        return results

    def _map_severity_to_level(self, severity: str) -> str:
        """Map severity to SARIF level."""
        mapping = {
            "critical": "error",
            "high": "error",
            "medium": "warning",
            "low": "note",
        }
        return mapping.get(severity, "note")

    def to_console(self) -> str:
        """
        Format report for console output.

        Returns:
            Formatted string for console
        """
        lines = []
        lines.append("=" * 60)
        lines.append(f"P.Mill Analysis Report")
        lines.append(f"File: {self.result.file_path}")
        lines.append(f"Analysis ID: {self.result.analysis_id}")
        lines.append(f"Timestamp: {self.result.timestamp.isoformat()}")
        lines.append("=" * 60)
        lines.append("")

        # Summary
        summary = self.result.summary
        if "error" in summary:
            lines.append(f"Error: {summary['error']}")
            return "\n".join(lines)

        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Issues: {summary.get('total_issues', 0)}")
        lines.append(f"Functions: {summary.get('functions_count', 0)}")
        lines.append(f"Classes: {summary.get('classes_count', 0)}")
        lines.append("")

        # By severity
        by_severity = summary.get("by_severity", {})
        if by_severity:
            lines.append("By Severity:")
            for sev, count in by_severity.items():
                if count > 0:
                    lines.append(f"  {sev.upper()}: {count}")
            lines.append("")

        # By category
        by_category = summary.get("by_category", {})
        if by_category:
            lines.append("By Category:")
            for cat, count in by_category.items():
                if count > 0:
                    lines.append(f"  {cat}: {count}")
            lines.append("")

        # Security issues (critical)
        if self.result.security_issues:
            lines.append("SECURITY ISSUES")
            lines.append("-" * 40)
            for issue in self.result.security_issues[:5]:  # Show first 5
                lines.append(f"  [{issue.get('severity', '?').upper()}] {issue.get('type', 'unknown')}")
                lines.append(f"    Line {issue.get('line', '?')}: {issue.get('description', '')}")
            if len(self.result.security_issues) > 5:
                lines.append(f"  ... and {len(self.result.security_issues) - 5} more")
            lines.append("")

        return "\n".join(lines)

    def to_html(self) -> str:
        """
        Generate HTML report.

        Returns:
            HTML string
        """
        html = """<!DOCTYPE html>
<html>
<head>
    <title>P.Mill Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f4f4f4; padding: 15px; border-radius: 5px; }}
        .issue {{ margin: 10px 0; padding: 10px; border-left: 3px solid #ccc; }}
        .issue.critical {{ border-left-color: #d32f2f; }}
        .issue.high {{ border-left-color: #f57c00; }}
        .issue.medium {{ border-left-color: #fbc02d; }}
        .issue.low {{ border-left-color: #388e3c; }}
        .issue-type {{ font-weight: bold; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>P.Mill Analysis Report</h1>
    <p><strong>File:</strong> {file_path}</p>
    <p><strong>Analysis ID:</strong> {analysis_id}</p>
    <p><strong>Timestamp:</strong> {timestamp}</p>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Issues:</strong> {total_issues}</p>
        <p><strong>Functions:</strong> {functions_count}</p>
        <p><strong>Classes:</strong> {classes_count}</p>
    </div>

    {issues_html}
</body>
</html>
"""

        # Build issues HTML
        issues_html = ""
        all_issues = (
            self.result.security_issues +
            self.result.performance_issues +
            self.result.maintainability_issues +
            self.result.logic_issues
        )

        # Group by severity
        critical_issues = [i for i in all_issues if i.get("severity") == "critical"]
        high_issues = [i for i in all_issues if i.get("severity") == "high"]
        medium_issues = [i for i in all_issues if i.get("severity") == "medium"]
        low_issues = [i for i in all_issues if i.get("severity") == "low"]

        if critical_issues:
            issues_html += "<h2>Critical Issues</h2>"
            for issue in critical_issues:
                issues_html += f"""<div class="issue critical">
    <div class="issue-type">{issue.get('type', 'unknown')}</div>
    <p><strong>Line:</strong> {issue.get('line', '?')}</p>
    <p>{issue.get('description', '')}</p>
</div>"""

        # Fill in template
        return html.format(
            file_path=self.result.file_path,
            analysis_id=self.result.analysis_id,
            timestamp=self.result.timestamp.isoformat(),
            total_issues=self.result.summary.get("total_issues", 0),
            functions_count=self.result.summary.get("functions_count", 0),
            classes_count=self.result.summary.get("classes_count", 0),
            issues_html=issues_html or "<p>No issues found.</p>",
        )

    def _build_report_dict(self) -> Dict[str, Any]:
        """Build complete report dict."""
        return {
            "analysis_id": self.result.analysis_id,
            "timestamp": self.result.timestamp.isoformat(),
            "file_path": self.result.file_path,
            "language": self.result.language,
            "code_hash": self.result.code_hash,
            "summary": self.result.summary,
            "structure": {
                "functions": len(self.result.structure.functions) if self.result.structure else 0,
                "classes": len(self.result.structure.classes) if self.result.structure else 0,
                "imports": len(self.result.structure.imports) if self.result.structure else 0,
            } if self.result.structure else {},
            "issues": {
                "logic": self.result.logic_issues,
                "security": self.result.security_issues,
                "performance": self.result.performance_issues,
                "maintainability": self.result.maintainability_issues,
            },
            "contracts": self.result.contracts,
            "invariants": self.result.invariants,
            "security_boundaries": {
                "input": self.result.input_boundaries,
                "output": self.result.output_boundaries,
                "privilege": self.result.privilege_boundaries,
                "trust_levels": self.result.trust_levels,
            },
        }


def export_report(
    result: AnalysisResult,
    format: str = "json",
    output_path: Optional[str] = None,
) -> str:
    """
    Export analysis report in specified format.

    Args:
        result: AnalysisResult to export
        format: Output format (json, sarif, console, html)
        output_path: Optional path to save report

    Returns:
        Report content
    """
    exporter = ReportExporter(result)

    if format == "json":
        content = exporter.to_json()
    elif format == "sarif":
        sarif_dict = exporter.to_sarif()
        content = json.dumps(sarif_dict, indent=2)
    elif format == "console":
        content = exporter.to_console()
    elif format == "html":
        content = exporter.to_html()
    else:
        raise ValueError(f"Unknown format: {format}")

    if output_path:
        Path(output_path).write_text(content)

    return content


def format_console_report(result: AnalysisResult) -> str:
    """
    Format analysis result for console output.

    Args:
        result: AnalysisResult to format

    Returns:
        Formatted string
    """
    return ReportExporter(result).to_console()
