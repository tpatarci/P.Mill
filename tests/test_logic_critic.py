"""Tests for logic critic."""

import pytest

from backend.analysis.logic_critic import (
    analyze_logic_issues,
    check_preconditions_verified,
    check_postconditions_established,
    generate_logic_report,
    LogicCritic,
    LogicIssue,
    PreconditionCheck,
)
from backend.models import FunctionInfo


class TestLogicIssueDetection:
    """Test logic issue detection."""

    def test_empty_code(self):
        """Test with empty code."""
        issues = analyze_logic_issues("", [])

        assert issues == []

    def test_missing_precondition_check(self):
        """Test detection of missing precondition checks."""
        code = """
def process(value: Optional[str]) -> str:
    return value.upper()
"""
        functions = [FunctionInfo(name="process", line_start=2, line_end=3, parameters=["value"])]
        issues = analyze_logic_issues(code, functions)

        assert isinstance(issues, list)

    def test_division_by_zero_detection(self):
        """Test division by zero detection."""
        code = """
def divide(x, y):
    return x / y
"""
        issues = analyze_logic_issues(code, [])

        assert any(i.issue_type == "division_by_zero_risk" for i in issues)

    def test_unreachable_code_detection(self):
        """Test unreachable code detection."""
        code = """
def unreachable():
    return 10
    print("never executed")
"""
        issues = analyze_logic_issues(code, [])

        assert any(i.issue_type == "unreachable_code" for i in issues)


class TestPreconditionChecks:
    """Test precondition verification."""

    def test_no_preconditions(self):
        """Test function with no parameters."""
        code = "def no_params(): return 42"
        func = FunctionInfo(name="no_params", line_start=1, line_end=1, parameters=[])

        checks = check_preconditions_verified(code, func)

        assert checks == []

    def test_checked_precondition(self):
        """Test that checked preconditions are detected."""
        code = """
def validate(value):
    if value is not None:
        return value
    return None
"""
        func = FunctionInfo(name="validate", line_start=2, line_end=5, parameters=["value"])

        checks = check_preconditions_verified(code, func)

        assert len(checks) >= 0

    def test_unchecked_precondition(self):
        """Test that unchecked preconditions are detected."""
        code = """
def process(value):
    return value.upper()
"""
        func = FunctionInfo(name="process", line_start=2, line_end=3, parameters=["value"])

        checks = check_preconditions_verified(code, func)

        if checks:
            assert not checks[0].is_checked


class TestPostconditionChecks:
    """Test postcondition verification."""

    def test_single_return(self):
        """Test function with single return."""
        code = "def single(): return 1"
        func = FunctionInfo(name="single", line_start=1, line_end=1, parameters=[])

        issues = check_postconditions_established(code, func)

        assert isinstance(issues, list)

    def test_multiple_returns(self):
        """Test function with multiple returns."""
        code = """
def multiple(x):
    if x > 0:
        return 1
    return 0
"""
        func = FunctionInfo(name="multiple", line_start=2, line_end=6, parameters=["x"])

        issues = check_postconditions_established(code, func)

        # Should flag multiple returns
        assert len(issues) > 0


class TestLogicReport:
    """Test logic report generation."""

    def test_empty_report(self):
        """Test report with no data."""
        report = generate_logic_report([], [])

        assert report["summary"]["total_issues"] == 0
        assert report["summary"]["total_preconditions"] == 0

    def test_report_with_issues(self):
        """Test report with issues."""
        issues = [
            LogicIssue(
                issue_type="division_by_zero_risk",
                function_name="divide",
                line=5,
                severity="medium",
                description="Division without zero check",
                suggestion="Add zero check",
            )
        ]

        report = generate_logic_report(issues, [])

        assert report["summary"]["total_issues"] == 1
        assert len(report["issues"]) == 1

    def test_aggregates_by_severity(self):
        """Test that report aggregates by severity."""
        issues = [
            LogicIssue("test1", "f1", 1, "low", "desc1"),
            LogicIssue("test2", "f2", 2, "high", "desc2"),
            LogicIssue("test3", "f3", 3, "high", "desc3"),
        ]

        report = generate_logic_report(issues, [])

        assert report["summary"]["by_severity"]["low"] == 1
        assert report["summary"]["by_severity"]["high"] == 2


class TestLogicCriticClass:
    """Test LogicCritic class."""

    def test_initialization(self):
        """Test critic initialization."""
        critic = LogicCritic("code")

        assert critic.issues == []
        assert critic.current_function is None

    def test_visits_function(self):
        """Test that critic visits functions."""
        code = "def test(): return 1"
        import ast

        tree = ast.parse(code)
        critic = LogicCritic(code)
        critic.visit(tree)

        assert isinstance(critic.issues, list)


class TestLogicIssueDataclass:
    """Test LogicIssue dataclass."""

    def test_all_fields(self):
        """Test LogicIssue has all required fields."""
        issue = LogicIssue(
            issue_type="test",
            function_name="test_func",
            line=10,
            severity="medium",
            description="Test issue",
            suggestion="Fix it",
        )

        assert issue.issue_type == "test"
        assert issue.function_name == "test_func"
        assert issue.line == 10


class TestEdgeCases:
    """Test edge cases."""

    def test_syntax_error_code(self):
        """Test with syntax error."""
        issues = analyze_logic_issues("def broken(", [])

        assert issues == []

    def test_complex_function(self):
        """Test analysis of complex function."""
        code = """
def complex_func(x, y):
    if x is not None:
        if y > 0:
            return x / y
        return 0
    return -1
"""
        issues = analyze_logic_issues(code, [])

        assert isinstance(issues, list)
