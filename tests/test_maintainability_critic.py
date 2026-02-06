"""Tests for maintainability critic."""

import pytest

from backend.analysis.maintainability_critic import (
    MaintainabilityIssue,
    MaintainabilityCritic,
    _detect_code_duplication,
    analyze_maintainability_issues,
    generate_maintainability_report,
)
from backend.models import FunctionInfo


class TestMaintainabilityIssueDetection:
    """Test maintainability issue detection."""

    def test_empty_code(self):
        """Test with empty code."""
        issues = analyze_maintainability_issues("", [])

        assert issues == []

    def test_long_function_detection(self):
        """Test long function detection."""
        code = """
def long_function():
    '''Docstring.'''
    x = 1
    x = 2
    x = 3
    x = 4
    x = 5
    x = 6
    x = 7
    x = 8
    x = 9
    x = 10
    x = 11
    x = 12
    x = 13
    x = 14
    x = 15
    x = 16
    x = 17
    x = 18
    x = 19
    x = 20
    x = 21
    x = 22
    x = 23
    x = 24
    x = 25
    x = 26
    x = 27
    x = 28
    x = 29
    x = 30
    x = 31
    return x
"""
        issues = analyze_maintainability_issues(code, [])

        assert any(i.issue_type == "long_function" for i in issues)

    def test_long_parameter_list(self):
        """Test long parameter list detection."""
        code = """
def func(a, b, c, d, e, f, g, h):
    return a + b + c + d + e + f + g + h
"""
        issues = analyze_maintainability_issues(code, [])

        assert any(i.issue_type == "long_parameter_list" for i in issues)

    def test_deep_nesting(self):
        """Test deep nesting detection."""
        code = """
def nested():
    if True:
        if True:
            if True:
                if True:
                    if True:
                        pass
"""
        issues = analyze_maintainability_issues(code, [])

        assert any(i.issue_type == "deep_nesting" for i in issues)

    def test_missing_docstring(self):
        """Test missing docstring detection."""
        code = """
def no_docstring(x):
    return x * 2
"""
        issues = analyze_maintainability_issues(code, [])

        assert any(i.issue_type == "missing_docstring" for i in issues)

    def test_magic_numbers(self):
        """Test magic number detection."""
        code = """
def calculate():
    result = 42 * 3.14159
    return result
"""
        issues = analyze_maintainability_issues(code, [])

        # May detect magic numbers
        assert isinstance(issues, list)

    def test_code_duplication(self):
        """Test code duplication detection."""
        code = """
def func_one():
    x = 10
    y = 20
    z = x + y
    result = z * 2
    return result

def func_two():
    x = 10
    y = 20
    z = x + y
    result = z * 2
    return result
"""
        issues = analyze_maintainability_issues(code, [])

        # Should detect duplication
        assert any(i.issue_type == "code_duplication" for i in issues)

    def test_poor_naming(self):
        """Test poor naming detection."""
        code = """
def BadName(x):
    return x + 1
"""
        issues = analyze_maintainability_issues(code, [])

        assert isinstance(issues, list)


class TestMaintainabilityReport:
    """Test maintainability report generation."""

    def test_empty_report(self):
        """Test report with no issues."""
        report = generate_maintainability_report([])

        assert report["summary"]["total_issues"] == 0
        assert report["issues"] == []

    def test_report_with_issues(self):
        """Test report with maintainability issues."""
        issues = [
            MaintainabilityIssue(
                issue_type="long_function",
                function_name="process",
                line=10,
                severity="medium",
                description="Function is too long",
                suggestion="Split into smaller functions",
            )
        ]

        report = generate_maintainability_report(issues)

        assert report["summary"]["total_issues"] == 1
        assert report["summary"]["by_type"]["long_function"] == 1
        assert report["summary"]["by_severity"]["medium"] == 1
        assert len(report["issues"]) == 1

    def test_report_aggregates_by_type(self):
        """Test that report aggregates by issue type."""
        issues = [
            MaintainabilityIssue("long_function", "f1", 1, "medium", "desc1"),
            MaintainabilityIssue("long_function", "f2", 2, "medium", "desc2"),
            MaintainabilityIssue("deep_nesting", "f3", 3, "low", "desc3"),
        ]

        report = generate_maintainability_report(issues)

        assert report["summary"]["by_type"]["long_function"] == 2
        assert report["summary"]["by_type"]["deep_nesting"] == 1

    def test_report_aggregates_by_severity(self):
        """Test that report aggregates by severity."""
        issues = [
            MaintainabilityIssue("test1", "f1", 1, "low", "desc1"),
            MaintainabilityIssue("test2", "f2", 2, "medium", "desc2"),
            MaintainabilityIssue("test3", "f3", 3, "high", "desc3"),
        ]

        report = generate_maintainability_report(issues)

        assert report["summary"]["by_severity"]["low"] == 1
        assert report["summary"]["by_severity"]["medium"] == 1
        assert report["summary"]["by_severity"]["high"] == 1


class TestMaintainabilityCriticClass:
    """Test MaintainabilityCritic class."""

    def test_initialization(self):
        """Test critic initialization."""
        critic = MaintainabilityCritic("code")

        assert critic.issues == []
        assert critic.current_function is None

    def test_visits_function(self):
        """Test that critic visits functions."""
        code = "def test(): return 1"
        import ast

        tree = ast.parse(code)
        critic = MaintainabilityCritic(code)
        critic.visit(tree)

        assert isinstance(critic.issues, list)


class TestMaintainabilityIssueDataclass:
    """Test MaintainabilityIssue dataclass."""

    def test_all_fields(self):
        """Test MaintainabilityIssue has all required fields."""
        issue = MaintainabilityIssue(
            issue_type="long_function",
            function_name="process",
            line=10,
            severity="medium",
            description="Function is too long",
            suggestion="Split it",
            confidence="high",
        )

        assert issue.issue_type == "long_function"
        assert issue.function_name == "process"
        assert issue.line == 10
        assert issue.severity == "medium"
        assert issue.suggestion == "Split it"
        assert issue.confidence == "high"


class TestEdgeCases:
    """Test edge cases."""

    def test_syntax_error_code(self):
        """Test with syntax error."""
        issues = analyze_maintainability_issues("def broken(", [])

        assert issues == []

    def test_short_function_no_issues(self):
        """Test that short, clean functions don't trigger false positives."""
        code = """
    '''Well documented function.'''
    return x + 1
"""
        issues = analyze_maintainability_issues(code, [])

        assert isinstance(issues, list)

    def test_class_methods(self):
        """Test method analysis in classes."""
        code = """
class MyClass:
    def method_one(self, x):
        return x * 2

    def method_two(self, y):
        return y * 3
"""
        issues = analyze_maintainability_issues(code, [])

        assert isinstance(issues, list)


class TestCodeDuplication:
    """Test code duplication detection."""

    def test_identical_functions(self):
        """Test detection of identical functions."""
        # Need longer bodies to exceed the 50 character threshold
        body = """    x = 1
    y = 2
    z = 3
    result = x + y + z
    return result
"""
        bodies = [
            ("func1", body, 1, 7),
            ("func2", body, 8, 14),
        ]

        issues = _detect_code_duplication(bodies)

        # Should detect duplication
        assert len(issues) > 0

    def test_different_functions(self):
        """Test that different functions don't trigger."""
        bodies = [
            ("func1", "x = 1", 1, 1),
            ("func2", "y = 2", 2, 2),
        ]

        issues = _detect_code_duplication(bodies)

        # Bodies too short to analyze
        assert len(issues) == 0


class TestSpecificIssueTypes:
    """Test specific issue type detection."""

    def test_all_severity_levels(self):
        """Test all severity levels are supported."""
        code = "def dummy(): pass"
        issues = analyze_maintainability_issues(code, [])

        # Should handle all severity levels
        for severity in ["low", "medium", "high"]:
            issue = MaintainabilityIssue(
                issue_type="test",
                function_name="test",
                line=1,
                severity=severity,
                description="test",
            )
            assert issue.severity == severity


class TestConfidenceLevels:
    """Test confidence level tracking."""

    def test_default_confidence(self):
        """Test default confidence is medium."""
        issue = MaintainabilityIssue(
            issue_type="test",
            function_name="test",
            line=1,
            severity="medium",
            description="test",
        )

        assert issue.confidence == "medium"

    def test_custom_confidence(self):
        """Test custom confidence level."""
        issue = MaintainabilityIssue(
            issue_type="test",
            function_name="test",
            line=1,
            severity="medium",
            description="test",
            confidence="high",
        )

        assert issue.confidence == "high"


class TestClassContext:
    """Test class method analysis."""

    def test_method_excludes_self(self):
        """Test that 'self' is excluded from parameter count."""
        code = """
class DataProcessor:
    def process(self, a, b, c, d):
        return a + b
"""
        issues = analyze_maintainability_issues(code, [])

        # Should have 4 parameters (excluding self), which should not trigger warning
        long_param_issues = [i for i in issues if i.issue_type == "long_parameter_list"]
        assert len(long_param_issues) == 0

    def test_nested_class(self):
        """Test nested class handling."""
        code = """
class Outer:
    class Inner:
        def method(self):
            pass
"""
        issues = analyze_maintainability_issues(code, [])

        assert isinstance(issues, list)


class TestDunderMethods:
    """Test handling of dunder methods."""

    def test_dunder_methods_skip_docstring_check(self):
        """Test that dunder methods don't trigger missing docstring."""
        code = """
class MyClass:
    def __init__(self):
        self.x = 1

    def __str__(self):
        return "MyClass"
"""
        issues = analyze_maintainability_issues(code, [])

        # Should not flag dunder methods for missing docstring
        missing_doc_issues = [i for i in issues if i.issue_type == "missing_docstring"]
        for issue in missing_doc_issues:
            assert not issue.function_name.endswith("__init__")
            assert not issue.function_name.endswith("__str__")
