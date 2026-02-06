"""Security critics for vulnerability detection.

This module detects:
- SQL injection vulnerabilities
- Command injection risks
- XSS vulnerabilities
- Path traversal issues
- Authentication/authorization issues
- Input validation problems
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import List, Optional

import structlog

from backend.models import FunctionInfo

logger = structlog.get_logger()


@dataclass
class SecurityIssue:
    """A security vulnerability found."""

    vuln_type: str  # "sql_injection", "command_injection", etc.
    function_name: str
    line: int
    severity: str  # "low", "medium", "high", "critical"
    description: str
    suggestion: Optional[str] = None
    confidence: str = "medium"


class SecurityCritic(ast.NodeVisitor):
    """Detect security vulnerabilities."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.issues: List[SecurityIssue] = []
        self.current_function: Optional[str] = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        self.current_function = node.name

        self._check_sql_injection(node)
        self._check_command_injection(node)
        self._check_xss(node)
        self._check_path_traversal(node)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self.visit_FunctionDef(node)

    def _check_sql_injection(self, node: ast.FunctionDef) -> None:
        """Check for SQL injection vulnerabilities."""
        sql_keywords = [
            "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
            "CREATE", "TRUNCATE", "GRANT", "REVOKE", "EXECUTE"
        ]

        for child in ast.walk(node):
            # Check for string concatenation with SQL
            if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Mod):
                # Check if right side contains user input
                left = ast.unparse(child.left).lower()
                right = ast.unparse(child.right)

                # Check for SQL keywords in format string
                has_sql = any(kw.lower() in left for kw in sql_keywords)

                if has_sql and _is_likely_user_input(right):
                    self.issues.append(
                        SecurityIssue(
                            vuln_type="sql_injection",
                            function_name=self.current_function,
                            line=child.lineno,
                            severity="critical",
                            description="SQL query format string with potential user input",
                            suggestion="Use parameterized queries instead",
                        )
                    )

            # Check for direct execute with user input
            if isinstance(child, ast.Call):
                func_name = ast.unparse(child.func)
                if "execute" in func_name.lower():
                    # Check if this is a parameterized query (has tuple as second arg)
                    is_parameterized = len(child.args) > 1 and isinstance(child.args[1], (ast.Tuple, ast.List))

                    if not is_parameterized:
                        # Not parameterized - check arguments
                        for arg in child.args:
                            arg_str = ast.unparse(arg)
                            if _is_likely_user_input(arg_str):
                                self.issues.append(
                                    SecurityIssue(
                                        vuln_type="sql_injection",
                                        function_name=self.current_function,
                                        line=child.lineno,
                                        severity="critical",
                                        description=f"SQL execute with potential user input: {arg_str}",
                                        suggestion="Use parameterized queries",
                                    )
                                )

    def _check_command_injection(self, node: ast.FunctionDef) -> None:
        """Check for command injection vulnerabilities."""
        dangerous_funcs = ["system", "popen", "subprocess.run", "subprocess.call",
                          "subprocess.Popen", "os.system", "os.popen"]

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func_name = ast.unparse(child.func)

                # Check for dangerous functions
                if any(df in func_name for df in dangerous_funcs):
                    # Check if arguments might be user input OR are variables
                    for arg in child.args:
                        arg_str = ast.unparse(arg)
                        # Flag if: 1) looks like user input, or 2) is a variable (not literal)
                        # Variables from external sources are risky
                        is_variable = isinstance(arg, ast.Name) or (
                            isinstance(arg, ast.Attribute) and not isinstance(arg.value, ast.Constant)
                        )
                        if _is_likely_user_input(arg_str) or is_variable:
                            self.issues.append(
                                SecurityIssue(
                                    vuln_type="command_injection",
                                    function_name=self.current_function,
                                    line=child.lineno,
                                    severity="critical",
                                    description=f"Command execution with potential user input: {func_name}({arg_str})",
                                    suggestion="Use subprocess.run with list of arguments, or validate input",
                                )
                            )

    def _check_xss(self, node: ast.FunctionDef) -> None:
        """Check for XSS vulnerabilities."""
        # Look for HTML output without escaping
        for child in ast.walk(node):
            if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Add):
                # Check for HTML concatenation
                left = ast.unparse(child.left)
                if "<" in left and ">" in left:
                    # Potential HTML output
                    right = ast.unparse(child.right)
                    if _is_likely_user_input(right):
                        self.issues.append(
                            SecurityIssue(
                                vuln_type="xss",
                                function_name=self.current_function,
                                line=child.lineno,
                                severity="high",
                                description="HTML output with potential unescaped user input",
                                suggestion="Use proper HTML escaping (e.g., markupsafe or html.escape)",
                            )
                        )

    def _check_path_traversal(self, node: ast.FunctionDef) -> None:
        """Check for path traversal vulnerabilities."""
        dangerous_patterns = ["open(", "Path(", "os.path.join"]

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func_name = ast.unparse(child.func)

                if any(dp in func_name for dp in dangerous_patterns):
                    for arg in child.args:
                        arg_str = ast.unparse(arg)
                        if _is_likely_user_input(arg_str):
                            self.issues.append(
                                SecurityIssue(
                                    vuln_type="path_traversal",
                                    function_name=self.current_function,
                                    line=child.lineno,
                                    severity="medium",
                                    description=f"File operation with potential user input: {func_name}({arg_str})",
                                    suggestion="Validate and sanitize file paths, use os.path.normpath",
                                )
                            )


def _is_likely_user_input(expr: str) -> bool:
    """Check if expression is likely user input."""
    user_input_patterns = [
        "request.", "input", "form.", "args.", "params.", "query", "body",
        "user", "data", "json", "xml", "html"
    ]

    expr_lower = expr.lower()
    return any(pattern.lower() in expr_lower for pattern in user_input_patterns)


def analyze_security_issues(
    source_code: str,
    functions: List[FunctionInfo],
) -> List[SecurityIssue]:
    """
    Analyze code for security vulnerabilities.

    Args:
        source_code: Python source code
        functions: List of functions to analyze

    Returns:
        List of SecurityIssue objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    critic = SecurityCritic(source_code)
    critic.visit(tree)

    return critic.issues


def generate_security_report(issues: List[SecurityIssue]) -> dict:
    """
    Generate security analysis report.

    Args:
        issues: List of security issues

    Returns:
        Dict with summary and details
    """
    # Count by vulnerability type
    type_counts: dict[str, int] = {}
    for issue in issues:
        type_counts[issue.vuln_type] = type_counts.get(issue.vuln_type, 0) + 1

    # Count by severity
    severity_counts: dict[str, int] = {}
    for issue in issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

    return {
        "summary": {
            "total_issues": len(issues),
            "by_type": type_counts,
            "by_severity": severity_counts,
        },
        "issues": [
            {
                "type": issue.vuln_type,
                "function": issue.function_name,
                "line": issue.line,
                "severity": issue.severity,
                "description": issue.description,
                "suggestion": issue.suggestion,
            }
            for issue in issues
        ],
    }
