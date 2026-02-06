"""Logic critic for verifying code correctness.

This module checks for:
- Preconditions are checked
- Postconditions are established
- Null/None dereferences
- Array bounds issues
- Division by zero risks
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

from backend.models import FunctionInfo

logger = structlog.get_logger()


@dataclass
class LogicIssue:
    """A logic issue found by the critic."""

    issue_type: str  # "missing_precondition_check", "none_dereference", etc.
    function_name: str
    line: int
    severity: str  # "low", "medium", "high", "critical"
    description: str
    suggestion: Optional[str] = None
    confidence: str = "medium"


@dataclass
class PreconditionCheck:
    """A precondition that should be verified."""

    parameter: str
    condition: str
    line: int
    is_checked: bool


class LogicCritic(ast.NodeVisitor):
    """Critic code for logical issues."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.issues: List[LogicIssue] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None

        # Track variable states
        self.nullable_vars: Set[str] = set()
        self.checked_vars: Set[str] = set()
        self.assigned_vars: Dict[str, int] = {}  # var -> line assigned

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

        # Analyze function for logical issues
        self._check_preconditions(node)
        self._check_none_dereferences(node)
        self._check_division_by_zero(node)
        self._check_array_bounds(node)
        self._check_unreachable_code(node)

        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self.visit_FunctionDef(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        """Track comparison checks."""
        # Track variables being compared for None
        if isinstance(node.ops, list) and len(node.ops) > 0:
            op = node.ops[0]
            if isinstance(op, (ast.Is, ast.IsNot)):
                if isinstance(node.left, ast.Name):
                    if isinstance(node.comparators[0], ast.Constant) and isinstance(node.comparators[0].value, type(None)):
                        self.checked_vars.add(node.left.id)
                    elif isinstance(node.comparators[0], ast.NameConstant):  # Python 3.8+
                        self.checked_vars.add(node.left.id)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Track variable assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.assigned_vars[target.id] = node.lineno

        self.generic_visit(node)

    def _check_preconditions(self, node: ast.FunctionDef) -> None:
        """Check if preconditions are verified."""
        # Look for Optional parameters that aren't checked
        for arg in node.args.args:
            if arg.annotation:
                annotation = ast.unparse(arg.annotation)
                if "Optional" in annotation or "Union" in annotation or "|" in annotation:
                    param_name = arg.arg
                    # Check if this optional is used before checking
                    self._check_optional_usage(node, param_name, annotation)

    def _check_optional_usage(self, node: ast.FunctionDef, param_name: str, annotation: str) -> None:
        """Check if optional parameter is used without validation."""
        # Find all uses of the parameter
        first_use_line = None
        first_check_line = None

        for child in ast.walk(node):
            # Find first use
            if isinstance(child, ast.Name) and child.id == param_name:
                if first_use_line is None:
                    first_use_line = child.lineno

            # Find first check
            if isinstance(child, ast.Compare):
                for sub in ast.walk(child):
                    if isinstance(sub, ast.Name) and sub.id == param_name:
                        if first_check_line is None:
                            first_check_line = sub.lineno

        # If used before checking, flag it
        if first_use_line and (first_check_line is None or first_use_line < first_check_line):
            # Check if there's a guard clause pattern
            if first_check_line and first_check_line > first_use_line:
                self.issues.append(
                    LogicIssue(
                        issue_type="missing_precondition_check",
                        function_name=self.current_function or node.name,
                        line=first_use_line,
                        severity="medium",
                        description=f"Optional parameter '{param_name}' used before validation",
                        suggestion=f"Add guard clause: if {param_name} is not None before use",
                    )
                )

    def _check_none_dereferences(self, node: ast.FunctionDef) -> None:
        """Check for potential None dereferences."""
        # Find attribute accesses on potentially None variables
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute):
                if isinstance(child.value, ast.Name):
                    var_name = child.value.id
                    # Check if variable might be None
                    if var_name not in self.checked_vars:
                        # Look for assignment that might be None
                        if var_name in self.assigned_vars:
                            # Could be assigned from a function returning None
                            self.issues.append(
                                LogicIssue(
                                    issue_type="potential_none_dereference",
                                    function_name=self.current_function or node.name,
                                    line=child.lineno,
                                    severity="low",
                                    description=f"Variable '{var_name}' accessed without None check",
                                    suggestion=f"Add: if {var_name} is not None before accessing",
                                )
                            )

    def _check_division_by_zero(self, node: ast.FunctionDef) -> None:
        """Check for division by zero risks."""
        for child in ast.walk(node):
            if isinstance(child, ast.BinOp):
                if isinstance(child.op, ast.Div) or isinstance(child.op, ast.FloorDiv):
                    # Check if denominator is checked for zero
                    if isinstance(child.right, ast.Name):
                        denom = child.right.id
                        if denom not in self.checked_vars:
                            self.issues.append(
                                LogicIssue(
                                    issue_type="division_by_zero_risk",
                                    function_name=self.current_function or node.name,
                                    line=child.lineno,
                                    severity="medium",
                                    description=f"Division by variable '{denom}' without zero check",
                                    suggestion=f"Add guard: if {denom} != 0 before division",
                                )
                            )

    def _check_array_bounds(self, node: ast.FunctionDef) -> None:
        """Check for potential array bounds issues."""
        for child in ast.walk(node):
            if isinstance(child, ast.Subscript):
                # Check for unvalidated index access
                if isinstance(child.slice, ast.Index):
                    if isinstance(child.slice.value, ast.Name):
                        index_var = child.slice.value.id
                        # Check if index is bounded
                        if index_var not in self.checked_vars:
                            self.issues.append(
                                LogicIssue(
                                    issue_type="array_index_risk",
                                    function_name=self.current_function or node.name,
                                    line=child.lineno,
                                    severity="low",
                                    description=f"Array index '{index_var}' not validated against bounds",
                                    suggestion=f"Add: if 0 <= {index_var} < len(array) before access",
                                )
                            )
                elif isinstance(child.slice, ast.Slice):
                    # Check for unvalidated slice
                    if not child.slice.step:
                        # Missing upper bound check
                        self.issues.append(
                            LogicIssue(
                                issue_type="slice_risk",
                                function_name=self.current_function or node.name,
                                line=child.lineno,
                                severity="low",
                                description="Slice without bounds checking",
                                suggestion="Consider adding bounds validation for slice",
                            )
                        )

    def _check_unreachable_code(self, node: ast.FunctionDef) -> None:
        """Check for unreachable code."""
        # Look for code after return
        has_return = False
        for i, stmt in enumerate(node.body):
            if isinstance(stmt, ast.Return):
                has_return = True
            elif has_return and not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Code after return is unreachable
                self.issues.append(
                    LogicIssue(
                        issue_type="unreachable_code",
                        function_name=self.current_function or node.name,
                        line=stmt.lineno,
                        severity="low",
                        description="Unreachable code after return",
                        suggestion="Remove dead code",
                    )
                )


def analyze_logic_issues(
    source_code: str,
    functions: List[FunctionInfo],
) -> List[LogicIssue]:
    """
    Analyze code for logical issues.

    Args:
        source_code: Python source code
        functions: List of functions to analyze

    Returns:
        List of LogicIssue objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    critic = LogicCritic(source_code)
    critic.visit(tree)

    return critic.issues


def check_preconditions_verified(
    source_code: str,
    function: FunctionInfo,
) -> List[PreconditionCheck]:
    """
    Check if preconditions are verified in function.

    Args:
        source_code: Python source code
        function: FunctionInfo to check

    Returns:
        List of PreconditionCheck objects
    """
    checks: List[PreconditionCheck] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    # Find the function node
    func_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function.name:
            func_node = node
            break

    if not func_node:
        return []

    # Collect parameter names
    params = {arg.arg for arg in func_node.args.args}

    # Check for guard clauses at function start
    checked_params: Set[str] = set()

    for i, stmt in enumerate(func_node.body[:5]):  # Check first 5 statements
        if isinstance(stmt, ast.If):
            # Check if condition validates a parameter
            condition_vars = _get_names_in_expr(stmt.test)
            for var in condition_vars:
                if var in params:
                    checked_params.add(var)

    # Create precondition checks
    for param in params:
        is_checked = param in checked_params
        checks.append(
            PreconditionCheck(
                parameter=param,
                condition=f"{param} is valid",
                line=function.line_start,
                is_checked=is_checked,
            )
        )

    return checks


def check_postconditions_established(
    source_code: str,
    function: FunctionInfo,
) -> List[LogicIssue]:
    """
    Check if postconditions are established.

    Args:
        source_code: Python source code
        function: FunctionInfo to check

    Returns:
        List of LogicIssue objects for missing postconditions
    """
    issues: List[LogicIssue] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    # Find the function node
    func_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function.name:
            func_node = node
            break

    if not func_node:
        return issues

    # Check if function has multiple return paths
    return_count = 0
    for node in ast.walk(func_node):
        if isinstance(node, ast.Return):
            return_count += 1

    # If multiple return paths, check consistency
    if return_count > 1:
        issues.append(
            LogicIssue(
                issue_type="multiple_return_paths",
                function_name=function.name,
                line=function.line_start,
                severity="low",
                description=f"Function has {return_count} return paths, ensure consistency",
                suggestion="Consider using single return or ensuring all paths establish postconditions",
            )
        )

    return issues


def generate_logic_report(
    logic_issues: List[LogicIssue],
    preconditions: List[PreconditionCheck],
) -> dict:
    """
    Generate logic analysis report.

    Args:
        logic_issues: All logic issues found
        preconditions: Precondition checks

    Returns:
        Dict with summary and details
    """
    # Count by issue type
    type_counts: Dict[str, int] = {}
    for issue in logic_issues:
        type_counts[issue.issue_type] = type_counts.get(issue.issue_type, 0) + 1

    # Count by severity
    severity_counts: Dict[str, int] = {}
    for issue in logic_issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

    # Count precondition checks
    total_preconditions = len(preconditions)
    checked_preconditions = sum(1 for pc in preconditions if pc.is_checked)

    return {
        "summary": {
            "total_issues": len(logic_issues),
            "total_preconditions": total_preconditions,
            "checked_preconditions": checked_preconditions,
            "unchecked_preconditions": total_preconditions - checked_preconditions,
            "by_issue_type": type_counts,
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
            for issue in logic_issues
        ],
        "precondition_checks": [
            {
                "parameter": pc.parameter,
                "condition": pc.condition,
                "line": pc.line,
                "is_checked": pc.is_checked,
            }
            for pc in preconditions
        ],
    }


def _get_names_in_expr(expr: ast.AST) -> Set[str]:
    """Get all variable names in an expression."""
    names: Set[str] = set()
    for node in ast.walk(expr):
        if isinstance(node, ast.Name):
            names.add(node.id)
    return names
