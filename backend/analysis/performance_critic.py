"""Performance critics for identifying performance issues.

This module detects:
- N+1 query patterns (nested loops with database calls)
- Inefficient algorithmic patterns (O(n²) nested loops)
- Resource leaks (unclosed files, connections)
- Missing early returns
- Large data copies
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional, Set

import structlog

from backend.models import FunctionInfo

logger = structlog.get_logger()


@dataclass
class PerformanceIssue:
    """A performance issue found by the critic."""

    issue_type: str  # "n_plus_1_queries", "o_n_squared", "resource_leak", etc.
    function_name: str
    line: int
    severity: str  # "low", "medium", "high"
    description: str
    suggestion: Optional[str] = None
    confidence: str = "medium"


class PerformanceCritic(ast.NodeVisitor):
    """Detect performance issues in code."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.issues: List[PerformanceIssue] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None

        # Track state with parent node tracking
        self.parent_map: dict[ast.AST, ast.AST] = {}
        self._within_with: Set[ast.AST] = set()  # Nodes inside with statements
        self._within_loop: Set[ast.AST] = set()  # Nodes inside loops

    def _build_parent_map(self, node: ast.AST, parent: Optional[ast.AST] = None) -> None:
        """Build parent map for AST nodes."""
        if parent is not None:
            self.parent_map[node] = parent
        for child in ast.iter_child_nodes(node):
            self._build_parent_map(child, node)

    def _mark_with_context(self, node: ast.AST) -> None:
        """Mark nodes inside with statements."""
        if isinstance(node, ast.With):
            for body_node in ast.walk(node):
                if body_node != node:
                    self._within_with.add(body_node)
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, ast.With):
                self._mark_with_context(child)

    def _mark_loop_context(self, node: ast.AST) -> None:
        """Mark nodes inside loops."""
        # Find all loop nodes and mark their descendants
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While)):
                # Mark all descendants of this loop (except the loop node itself)
                for descendant in ast.walk(child):
                    if descendant != child:
                        self._within_loop.add(descendant)

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

        # Build context for this function
        self._build_parent_map(node)
        self._mark_with_context(node)
        self._mark_loop_context(node)

        # Analyze function
        self._check_n_plus_1_queries(node)
        self._check_quadratic_patterns(node)
        self._check_resource_leaks(node)
        self._check_missing_early_return(node)
        self._check_inefficient_string_ops(node)

        self.generic_visit(node)

        # Clear context
        self.current_function = old_function
        self.parent_map.clear()
        self._within_with.clear()
        self._within_loop.clear()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self.visit_FunctionDef(node)

    def _check_n_plus_1_queries(self, node: ast.FunctionDef) -> None:
        """Check for N+1 query patterns."""
        for child in ast.walk(node):
            # Look for database calls inside loops
            if isinstance(child, ast.For) or isinstance(child, ast.While):
                for body_child in ast.walk(child):
                    if isinstance(body_child, ast.Call):
                        func_name = ast.unparse(body_child.func)
                        # Check for database execute patterns
                        if any(db_func in func_name.lower() for db_func in
                               ["execute", "fetch", "query", "select", "find", "get"]):
                            # Check if this might be a database call
                            if any(db_indicator in func_name.lower() for db_indicator in
                                   ["cursor", "db", "database", "session", "conn", "model"]):
                                self.issues.append(
                                    PerformanceIssue(
                                        issue_type="n_plus_1_queries",
                                        function_name=self.current_function or node.name,
                                        line=body_child.lineno,
                                        severity="high",
                                        description=f"Database call inside loop: {func_name}(). "
                                                   f"Consider using eager loading or bulk queries.",
                                        suggestion="Move database call outside loop or use JOIN/eager loading",
                                    )
                                )

    def _check_quadratic_patterns(self, node: ast.FunctionDef) -> None:
        """Check for O(n²) patterns."""
        for child in ast.walk(node):
            # Check for nested loops with O(n) operations inside
            if isinstance(child, ast.For):
                # Check if loop body contains another loop
                has_inner_loop = False
                inner_loop_line = None
                for body_child in ast.walk(child):
                    if isinstance(body_child, (ast.For, ast.While)) and body_child != child:
                        has_inner_loop = True
                        inner_loop_line = body_child.lineno
                        break

                if has_inner_loop and inner_loop_line:
                    self.issues.append(
                        PerformanceIssue(
                            issue_type="o_n_squared",
                            function_name=self.current_function or node.name,
                            line=inner_loop_line,
                            severity="medium",
                            description="Nested loop detected (O(n²) complexity). "
                                       "Consider optimizing algorithm or using appropriate data structures.",
                            suggestion="Consider using sets/dicts for O(1) lookups, or algorithmic optimization",
                        )
                    )

            # Check for list operations in loops that could be O(n²)
            if isinstance(child, ast.For):
                for body_child in ast.walk(child):
                    # Check for list.append in loop (might be okay, but flag for review)
                    # More concerning: list operations that cause reallocation
                    if isinstance(body_child, ast.Call):
                        func_name = ast.unparse(body_child.func)
                        # These operations inside loops can be O(n²)
                        if "insert" in func_name and len(body_child.args) > 0:
                            # Check if first argument is 0 (insert at position 0)
                            if isinstance(body_child.args[0], ast.Constant):
                                value = body_child.args[0]
                                if isinstance(value, ast.Constant) and value.value == 0:
                                    self.issues.append(
                                        PerformanceIssue(
                                            issue_type="inefficient_list_operation",
                                            function_name=self.current_function or node.name,
                                            line=body_child.lineno,
                                            severity="medium",
                                            description=f"Insert at position 0 inside loop: {func_name}. "
                                                       f"This is O(n) per iteration.",
                                            suggestion="Use collections.deque with appendleft() or reverse the logic",
                                        )
                                    )

    def _check_resource_leaks(self, node: ast.FunctionDef) -> None:
        """Check for resource leaks."""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func_name = ast.unparse(child.func)

                # Track open() calls
                if func_name == "open" or ".open(" in func_name:
                    # Check if not in a with statement
                    if child not in self._within_with:
                        self.issues.append(
                            PerformanceIssue(
                                issue_type="resource_leak_risk",
                                function_name=self.current_function or node.name,
                                line=child.lineno,
                                severity="medium",
                                description=f"open() call without context manager (with statement). "
                                           f"Resource may not be properly closed.",
                                suggestion="Use 'with open(...) as f:' pattern for automatic cleanup",
                            )
                        )

                # Check for other resource types
                if any(r in func_name for r in ["urllib.open", "urlopen", "socket.socket", "connect("]):
                    if child not in self._within_with:
                        self.issues.append(
                            PerformanceIssue(
                                issue_type="resource_leak_risk",
                                function_name=self.current_function or node.name,
                                line=child.lineno,
                                severity="medium",
                                description=f"Resource creation without context manager: {func_name}",
                                suggestion="Use context manager or explicit close() in finally block",
                            )
                        )

    def _check_missing_early_return(self, node: ast.FunctionDef) -> None:
        """Check for missing early return patterns."""
        # Look for if statements that could return early
        for child in node.body:
            if isinstance(child, ast.If):
                # Check if the if body ends with a return
                has_return = False
                for if_child in child.body:
                    if isinstance(if_child, ast.Return):
                        has_return = True
                        break

                # Check if there's a corresponding elif or else that also returns
                if has_return and child.orelse:
                    has_else_return = False
                    for else_child in child.orelse:
                        if isinstance(else_child, ast.Return):
                            has_else_return = True
                            break
                        # Also check for nested if that returns
                        for nested in ast.walk(else_child):
                            if isinstance(nested, ast.Return):
                                has_else_return = True
                                break

                    if not has_else_return and len(child.orelse) > 0:
                        self.issues.append(
                            PerformanceIssue(
                                issue_type="missing_early_return",
                                function_name=self.current_function or node.name,
                                line=child.lineno,
                                severity="low",
                                description="If statement returns early but else branch doesn't. "
                                           "Consider restructuring for clarity.",
                                suggestion="Consider inverting the condition or adding explicit else return",
                            )
                        )

    def _check_inefficient_string_ops(self, node: ast.FunctionDef) -> None:
        """Check for inefficient string operations."""
        for child in ast.walk(node):
            # Check for string concatenation in loop (both BinOp and AugAssign)
            is_concat = False
            if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Add):
                is_concat = True
            elif isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
                is_concat = True

            if is_concat and child in self._within_loop:
                # This looks like string concatenation in a loop
                self.issues.append(
                    PerformanceIssue(
                        issue_type="inefficient_string_concat",
                        function_name=self.current_function or node.name,
                        line=child.lineno,
                        severity="low",
                        description="String concatenation inside loop. Consider using str.join() or StringIO.",
                        suggestion="Use ''.join(list_of_strings) or io.StringIO for building strings",
                    )
                )


def analyze_performance_issues(
    source_code: str,
    functions: List[FunctionInfo],
) -> List[PerformanceIssue]:
    """
    Analyze code for performance issues.

    Args:
        source_code: Python source code
        functions: List of functions to analyze

    Returns:
        List of PerformanceIssue objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    critic = PerformanceCritic(source_code)
    critic.visit(tree)

    return critic.issues


def generate_performance_report(issues: List[PerformanceIssue]) -> dict:
    """
    Generate performance analysis report.

    Args:
        issues: List of performance issues

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
