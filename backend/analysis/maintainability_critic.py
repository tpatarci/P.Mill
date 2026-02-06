"""Maintainability critic for code quality assessment.

This module detects:
- Code duplication
- Long functions
- Long parameter lists
- Deep nesting
- Magic numbers
- Poor naming
- Missing docstrings
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Set, Tuple

import structlog

from backend.models import FunctionInfo

logger = structlog.get_logger()


@dataclass
class MaintainabilityIssue:
    """A maintainability issue found by the critic."""

    issue_type: str  # "code_duplication", "long_function", "magic_number", etc.
    function_name: str
    line: int
    severity: str  # "low", "medium", "high"
    description: str
    suggestion: Optional[str] = None
    confidence: str = "medium"


class MaintainabilityCritic(ast.NodeVisitor):
    """Detect maintainability issues in code."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.issues: List[MaintainabilityIssue] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None

        # Track function bodies for duplication detection
        self.function_bodies: List[Tuple[str, str, int, int]] = []  # (name, body, start, end)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        old_function = self.current_function
        self.current_function = f"{self.current_class}.{node.name}" if self.current_class else node.name

        # Store function body for duplication analysis
        body_text = self._extract_function_body(node)
        self.function_bodies.append((self.current_function, body_text, node.lineno, node.end_lineno or node.lineno))

        # Analyze this function
        self._check_long_function(node)
        self._check_long_parameter_list(node)
        self._check_deep_nesting(node)
        self._check_missing_docstring(node)
        self._check_magic_numbers(node)
        self._check_poor_naming(node)

        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self.visit_FunctionDef(node)

    def _extract_function_body(self, node: ast.FunctionDef) -> str:
        """Extract function body as text."""
        try:
            start_line = node.lineno
            end_line = node.end_lineno or start_line
            # Use 0-indexing for list access
            lines = self.source_lines[start_line - 1:end_line]
            return "\n".join(lines)
        except (IndexError, AttributeError):
            return ""

    def _check_long_function(self, node: ast.FunctionDef) -> None:
        """Check for overly long functions."""
        # Count lines of code (excluding docstring)
        loc = 0
        in_docstring = False
        docstring_lines = 0

        for child in node.body:
            if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant):
                if isinstance(child.value, ast.Constant) and isinstance(child.value.value, str):
                    in_docstring = True
                    docstring_lines = self._count_docstring_lines(str(child.value.value))

        # Total lines in function
        total_lines = (node.end_lineno or node.lineno) - node.lineno
        effective_loc = total_lines - docstring_lines

        if effective_loc > 50:
            self.issues.append(
                MaintainabilityIssue(
                    issue_type="long_function",
                    function_name=self.current_function or node.name,
                    line=node.lineno,
                    severity="medium",
                    description=f"Function is {effective_loc} lines long (excluding docstring). "
                               f"Consider splitting into smaller functions.",
                    suggestion="Extract smaller helper functions to improve readability and testability",
                )
            )
        elif effective_loc > 30:
            self.issues.append(
                MaintainabilityIssue(
                    issue_type="long_function",
                    function_name=self.current_function or node.name,
                    line=node.lineno,
                    severity="low",
                    description=f"Function is {effective_loc} lines long. "
                               f"Approaching the threshold for maintainability.",
                    suggestion="Consider if this function could be simplified",
                )
            )

    def _count_docstring_lines(self, docstring: str) -> int:
        """Count lines in a docstring."""
        return docstring.count("\n") + 1

    def _check_long_parameter_list(self, node: ast.FunctionDef) -> None:
        """Check for functions with too many parameters."""
        param_count = len(node.args.args)
        # Exclude 'self' for methods
        if param_count > 0 and node.args.args[0].arg == "self":
            param_count -= 1

        if param_count > 7:
            self.issues.append(
                MaintainabilityIssue(
                    issue_type="long_parameter_list",
                    function_name=self.current_function or node.name,
                    line=node.lineno,
                    severity="high",
                    description=f"Function has {param_count} parameters. "
                               f"Consider using a configuration object or dataclass.",
                    suggestion="Group related parameters into a dataclass or config object",
                )
            )
        elif param_count > 5:
            self.issues.append(
                MaintainabilityIssue(
                    issue_type="long_parameter_list",
                    function_name=self.current_function or node.name,
                    line=node.lineno,
                    severity="medium",
                    description=f"Function has {param_count} parameters. "
                               f"This may indicate the function does too much.",
                    suggestion="Consider if some parameters could be grouped or if the function should be split",
                )
            )

    def _check_deep_nesting(self, node: ast.FunctionDef) -> None:
        """Check for deeply nested code."""
        max_depth = self._calculate_nesting_depth(node)

        if max_depth > 4:
            self.issues.append(
                MaintainabilityIssue(
                    issue_type="deep_nesting",
                    function_name=self.current_function or node.name,
                    line=node.lineno,
                    severity="medium",
                    description=f"Function has nesting depth of {max_depth}. "
                               f"Deep nesting makes code hard to read.",
                    suggestion="Extract nested blocks into separate functions with guard clauses",
                )
            )
        elif max_depth > 3:
            self.issues.append(
                MaintainabilityIssue(
                    issue_type="deep_nesting",
                    function_name=self.current_function or node.name,
                    line=node.lineno,
                    severity="low",
                    description=f"Function has nesting depth of {max_depth}.",
                    suggestion="Consider using early returns to reduce nesting",
                )
            )

    def _calculate_nesting_depth(self, node: ast.FunctionDef) -> int:
        """Calculate maximum nesting depth in function."""
        max_depth = 0

        def _depth(n: ast.AST, current: int) -> None:
            nonlocal max_depth
            max_depth = max(max_depth, current)
            for child in ast.iter_child_nodes(n):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.Match)):
                    _depth(child, current + 1)
                else:
                    _depth(child, current)

        _depth(node, 0)
        return max_depth

    def _check_missing_docstring(self, node: ast.FunctionDef) -> None:
        """Check for missing docstrings."""
        has_docstring = False

        # Check if first statement is a docstring
        if node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                if isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                    has_docstring = bool(first.value.value.strip())

        if not has_docstring:
            # Skip dunder methods and simple overrides
            if not (node.name.startswith("__") and node.name.endswith("__")):
                self.issues.append(
                    MaintainabilityIssue(
                        issue_type="missing_docstring",
                        function_name=self.current_function or node.name,
                        line=node.lineno,
                        severity="low",
                        description=f"Function '{node.name}' is missing a docstring.",
                        suggestion="Add a docstring describing the function's purpose, parameters, and return value",
                    )
                )

    def _check_magic_numbers(self, node: ast.FunctionDef) -> None:
        """Check for magic numbers in code."""
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
                # Skip common values
                if child.value in [0, 1, -1, 2, 100, 1000]:
                    continue
                # Skip if it's a simple comparison or small index
                if isinstance(child.value, int) and -10 <= child.value <= 10:
                    # Check context - if part of comparison with known patterns, skip
                    continue

                self.issues.append(
                    MaintainabilityIssue(
                        issue_type="magic_number",
                        function_name=self.current_function or node.name,
                        line=child.lineno,
                        severity="low",
                        description=f"Magic number {child.value} found in code.",
                        suggestion="Replace with a named constant for better readability",
                    )
                )

    def _check_poor_naming(self, node: ast.FunctionDef) -> None:
        """Check for poor naming conventions."""
        # Check function name
        if not self._is_good_name(node.name):
            self.issues.append(
                MaintainabilityIssue(
                    issue_type="poor_naming",
                    function_name=self.current_function or node.name,
                    line=node.lineno,
                    severity="low",
                    description=f"Function name '{node.name}' may not follow Python conventions.",
                    suggestion="Use lowercase_with_underscores for function names",
                )
            )

        # Check parameter names
        for arg in node.args.args:
            if not self._is_good_name(arg.arg) and arg.arg not in ["self", "cls"]:
                self.issues.append(
                    MaintainabilityIssue(
                        issue_type="poor_naming",
                        function_name=self.current_function or node.name,
                        line=node.lineno,
                        severity="low",
                        description=f"Parameter name '{arg.arg}' may not be descriptive.",
                        suggestion="Use descriptive names that describe the parameter's purpose",
                    )
                )

    def _is_good_name(self, name: str) -> bool:
        """Check if a name follows Python conventions."""
        # Should be snake_case
        if not re.match(r'^[a-z][a-z0-9_]*$', name):
            return False
        # Should not be too short
        if len(name) == 1 and name not in ["_", "x", "y", "z", "i", "j", "k"]:
            return False
        return True


def _detect_code_duplication(function_bodies: List[Tuple[str, str, int, int]]) -> List[MaintainabilityIssue]:
    """Detect duplicated code blocks."""
    issues: List[MaintainabilityIssue] = []

    # Compare each function body with each other
    for i, (name1, body1, start1, end1) in enumerate(function_bodies):
        for name2, body2, start2, end2 in function_bodies[i + 1:]:
            # Skip if bodies are too short
            if len(body1) < 50 or len(body2) < 50:
                continue

            # Calculate similarity
            similarity = SequenceMatcher(None, body1, body2).ratio()

            if similarity > 0.8:
                issues.append(
                    MaintainabilityIssue(
                        issue_type="code_duplication",
                        function_name=name1,
                        line=start1,
                        severity="medium",
                        description=f"Code duplication detected between '{name1}' and '{name2}'. "
                                   f"Similarity: {similarity:.0%}",
                        suggestion=f"Extract common code into a shared function. "
                                   f"See also: {name2} at line {start2}",
                    )
                )

    return issues


def analyze_maintainability_issues(
    source_code: str,
    functions: List[FunctionInfo],
) -> List[MaintainabilityIssue]:
    """
    Analyze code for maintainability issues.

    Args:
        source_code: Python source code
        functions: List of functions to analyze

    Returns:
        List of MaintainabilityIssue objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    critic = MaintainabilityCritic(source_code)
    critic.visit(tree)

    # Also check for code duplication
    duplication_issues = _detect_code_duplication(critic.function_bodies)
    critic.issues.extend(duplication_issues)

    return critic.issues


def generate_maintainability_report(issues: List[MaintainabilityIssue]) -> dict:
    """
    Generate maintainability analysis report.

    Args:
        issues: List of maintainability issues

    Returns:
        Dict with summary and details
    """
    # Count by issue type
    type_counts: dict[str, int] = {}
    for issue in issues:
        type_counts[issue.issue_type] = type_counts.get(issue.issue_type, 0) + 1

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
                "type": issue.issue_type,
                "function": issue.function_name,
                "line": issue.line,
                "severity": issue.severity,
                "description": issue.description,
                "suggestion": issue.suggestion,
            }
            for issue in issues
        ],
    }
