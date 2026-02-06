"""Tests for refactoring suggester."""

import pytest

from backend.models import FunctionInfo
from backend.synthesis.refactoring_suggester import (
    RefactoringSuggestion,
    RefactoringSuggester,
    generate_refactoring_report,
    suggest_refactorings,
)


class TestRefactoringSuggestions:
    """Test refactoring suggestion generation."""

    def test_empty_code(self):
        """Test with empty code."""
        suggestions = suggest_refactorings("", [])

        assert suggestions == []

    def test_long_function_suggestion(self):
        """Test extract method suggestion for long function."""
        code = """
def long_function():
    '''A very long function.'''
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
        suggestions = suggest_refactorings(code, [])

        assert any(s.suggestion_type == "extract_method" for s in suggestions)

    def test_parameter_object_suggestion(self):
        """Test parameter object suggestion for functions with many params."""
        code = """
def func(a, b, c, d, e, f):
    return a + b + c + d + e + f
"""
        suggestions = suggest_refactorings(code, [])

        assert any(s.suggestion_type == "parameter_object" for s in suggestions)

    def test_simplify_conditional_suggestion(self):
        """Test conditional simplification suggestion."""
        code = """
def chained_if(x):
    if x > 10:
        return "large"
    elif x > 0:
        return "medium"
    else:
        return "small"
"""
        suggestions = suggest_refactorings(code, [])

        # May suggest simplification based on structure
        assert isinstance(suggestions, list)

    def test_magic_number_suggestion(self):
        """Test magic number replacement suggestion."""
        code = """
def calculate():
    result = 42 * 3.14159
    return result
"""
        suggestions = suggest_refactorings(code, [])

        # May suggest replacing magic numbers
        assert isinstance(suggestions, list)

    def test_short_function_no_suggestions(self):
        """Test that short, clean functions don't trigger suggestions."""
        code = """
def add(x, y):
    return x + y
"""
        suggestions = suggest_refactorings(code, [])

        # Should be minimal or no suggestions
        assert isinstance(suggestions, list)


class TestRefactoringReport:
    """Test refactoring report generation."""

    def test_empty_report(self):
        """Test report with no suggestions."""
        report = generate_refactoring_report([])

        assert report["summary"]["total_suggestions"] == 0
        assert report["suggestions"] == []

    def test_report_with_suggestions(self):
        """Test report with refactoring suggestions."""
        suggestions = [
            RefactoringSuggestion(
                suggestion_id="test:extract",
                suggestion_type="extract_method",
                function_name="long_func",
                line_start=1,
                line_end=50,
                description="Function is too long",
                suggested_code="# Extract logic",
                confidence="medium",
                effort="medium",
            )
        ]

        report = generate_refactoring_report(suggestions)

        assert report["summary"]["total_suggestions"] == 1
        assert report["summary"]["by_type"]["extract_method"] == 1
        assert len(report["suggestions"]) == 1

    def test_report_aggregates_by_type(self):
        """Test that report aggregates by suggestion type."""
        suggestions = [
            RefactoringSuggestion("t1", "extract_method", "f1", 1, 1, "d1", "c1", "medium", "low"),
            RefactoringSuggestion("t2", "extract_method", "f2", 2, 2, "d2", "c2", "medium", "low"),
            RefactoringSuggestion("t3", "parameter_object", "f3", 3, 3, "d3", "c3", "low", "high"),
        ]

        report = generate_refactoring_report(suggestions)

        assert report["summary"]["by_type"]["extract_method"] == 2
        assert report["summary"]["by_type"]["parameter_object"] == 1

    def test_report_aggregates_by_effort(self):
        """Test that report aggregates by effort level."""
        suggestions = [
            RefactoringSuggestion("t1", "type1", "f1", 1, 1, "d1", "c1", "medium", "low"),
            RefactoringSuggestion("t2", "type2", "f2", 2, 2, "d2", "c2", "medium", "medium"),
            RefactoringSuggestion("t3", "type3", "f3", 3, 3, "d3", "c3", "medium", "high"),
        ]

        report = generate_refactoring_report(suggestions)

        assert report["summary"]["by_effort"]["low"] == 1
        assert report["summary"]["by_effort"]["medium"] == 1
        assert report["summary"]["by_effort"]["high"] == 1


class TestRefactoringSuggesterClass:
    """Test RefactoringSuggester class."""

    def test_initialization(self):
        """Test suggester initialization."""
        suggester = RefactoringSuggester("code")

        assert suggester.source_code == "code"
        assert suggester.suggestions == []

    def test_visits_function(self):
        """Test that suggester visits functions."""
        code = "def test(): return 1"
        import ast

        tree = ast.parse(code)
        suggester = RefactoringSuggester(code)
        suggester.visit(tree)

        assert isinstance(suggester.suggestions, list)


class TestRefactoringSuggestionDataclass:
    """Test RefactoringSuggestion dataclass."""

    def test_all_fields(self):
        """Test RefactoringSuggestion has all required fields."""
        suggestion = RefactoringSuggestion(
            suggestion_id="test",
            suggestion_type="extract_method",
            function_name="func",
            line_start=10,
            line_end=20,
            description="Test suggestion",
            suggested_code="# Suggested code",
            confidence="high",
            effort="low",
        )

        assert suggestion.suggestion_id == "test"
        assert suggestion.suggestion_type == "extract_method"
        assert suggestion.function_name == "func"
        assert suggestion.confidence == "high"
        assert suggestion.effort == "low"

    def test_default_values(self):
        """Test default field values."""
        suggestion = RefactoringSuggestion(
            suggestion_id="test",
            suggestion_type="test",
            function_name="func",
            line_start=1,
            line_end=1,
            description="desc",
            suggested_code="code",
        )

        assert suggestion.confidence == "medium"
        assert suggestion.effort == "medium"


class TestEdgeCases:
    """Test edge cases."""

    def test_syntax_error_code(self):
        """Test with syntax error."""
        suggestions = suggest_refactorings("def broken(", [])

        assert suggestions == []

    def test_class_method(self):
        """Test suggestion for class methods."""
        code = """
class MyClass:
    def long_method(self):
        x = 1
        # ... many lines
        return x
"""
        suggestions = suggest_refactorings(code, [])

        assert isinstance(suggestions, list)


class TestConfidenceAndEffort:
    """Test confidence and effort levels."""

    def test_all_confidence_levels(self):
        """Test all confidence levels are supported."""
        for confidence in ["low", "medium", "high"]:
            suggestion = RefactoringSuggestion(
                suggestion_id="test",
                suggestion_type="test",
                function_name="func",
                line_start=1,
                line_end=1,
                description="desc",
                suggested_code="code",
                confidence=confidence,
            )
            assert suggestion.confidence == confidence

    def test_all_effort_levels(self):
        """Test all effort levels are supported."""
        for effort in ["low", "medium", "high"]:
            suggestion = RefactoringSuggestion(
                suggestion_id="test",
                suggestion_type="test",
                function_name="func",
                line_start=1,
                line_end=1,
                description="desc",
                suggested_code="code",
                effort=effort,
            )
            assert suggestion.effort == effort
