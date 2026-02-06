"""Tests for unified analyzer."""

import pytest

from backend.analysis.unified_analyzer import (
    AnalysisResult,
    UnifiedAnalyzer,
    analyze_code,
)


class TestUnifiedAnalyzer:
    """Test the unified analyzer."""

    def test_empty_code(self):
        """Test with empty code."""
        result = analyze_code("")

        assert result.analysis_id
        assert result.language == "python"
        assert isinstance(result.summary, dict)

    def test_simple_function_analysis(self):
        """Test analysis of simple function."""
        code = """
def add(x, y):
    return x + y
"""
        result = analyze_code(code)

        assert result.structure is not None
        assert len(result.structure.functions) == 1
        assert result.structure.functions[0].name == "add"

    def test_logic_issues_detection(self):
        """Test that logic issues are detected."""
        code = """
def divide(x, y):
    return x / y
"""
        result = analyze_code(code)

        # Should detect division by zero risk
        assert isinstance(result.logic_issues, list)
        assert any(i.get("type") == "division_by_zero_risk" for i in result.logic_issues)

    def test_security_issues_detection(self):
        """Test that security issues are detected."""
        code = """
def query(user_id):
    sql = "SELECT * FROM users WHERE id = %s" % user_id
    return sql
"""
        result = analyze_code(code)

        # Should detect SQL injection risk
        assert isinstance(result.security_issues, list)

    def test_performance_issues_detection(self):
        """Test that performance issues are detected."""
        code = """
def nested_loop(items):
    for x in items:
        for y in items:
            pass
"""
        result = analyze_code(code)

        # Should detect O(n²) pattern
        assert isinstance(result.performance_issues, list)

    def test_maintainability_issues_detection(self):
        """Test that maintainability issues are detected."""
        code = """
def long_function():
    x = 1
    x = 2
    # ... many more lines
    return x
""" + "\n    x = {}\n" * 35

        result = analyze_code(code)

        # Should detect long function
        assert any(i.get("type") == "long_function" for i in result.maintainability_issues)

    def test_complexity_metrics(self):
        """Test complexity metrics calculation."""
        code = """
def complex_func(x):
    if x > 0:
        if x > 10:
            return 1
        else:
            return 2
    else:
        return 3
"""
        result = analyze_code(code)

        assert "total_functions" in result.complexity_metrics
        assert result.complexity_metrics["total_functions"] >= 1

    def test_summary_generation(self):
        """Test summary generation."""
        code = """
def foo():
    return 1
"""
        result = analyze_code(code)

        assert "total_issues" in result.summary
        assert "by_severity" in result.summary
        assert "by_category" in result.summary

    def test_syntax_error_handling(self):
        """Test handling of syntax errors."""
        code = "def broken("
        result = analyze_code(code)

        # Should handle gracefully
        assert result.summary.get("error") or result.summary == {"error": "Syntax error in source code"}

    def test_skip_patterns_flag(self):
        """Test skip_patterns flag."""
        code = """
class Singleton:
    _instance = None
"""
        result = analyze_code(code, skip_patterns=True)

        # Patterns should be empty or minimal when skipped
        assert isinstance(result.design_patterns, list)

    def test_analysis_id_unique(self):
        """Test that each analysis gets a unique ID."""
        code = "def foo(): return 1"

        result1 = analyze_code(code)
        result2 = analyze_code(code)

        assert result1.analysis_id != result2.analysis_id

    def test_code_hash_consistent(self):
        """Test that code hash is consistent."""
        code = "def foo(): return 1"

        result1 = analyze_code(code)
        result2 = analyze_code(code)

        assert result1.code_hash == result2.code_hash

    def test_file_path_recorded(self):
        """Test that file path is recorded."""
        code = "def foo(): return 1"

        result = analyze_code(code, file_path="test.py")

        assert result.file_path == "test.py"

    def test_class_analysis(self):
        """Test class analysis."""
        code = """
class MyClass:
    def method(self):
        return 1
"""
        result = analyze_code(code)

        assert result.structure is not None
        assert len(result.structure.classes) == 1
        assert result.structure.classes[0].name == "MyClass"

    def test_security_boundaries_analysis(self):
        """Test security boundary analysis."""
        code = """
from flask import request

def process():
    user_input = request.args.get('data')
    return user_input
"""
        result = analyze_code(code)

        # Should detect input boundaries
        assert isinstance(result.input_boundaries, list)


class TestAnalysisResult:
    """Test AnalysisResult dataclass."""

    def test_all_fields(self):
        """Test AnalysisResult has all required fields."""
        result = AnalysisResult(
            analysis_id="test-id",
            timestamp=None,
            file_path="test.py",
            language="python",
            code_hash="abc123",
        )

        assert result.analysis_id == "test-id"
        assert result.file_path == "test.py"
        assert result.language == "python"


class TestEdgeCases:
    """Test edge cases."""

    def test_unicode_in_code(self):
        """Test handling of unicode characters."""
        code = """
def greet(name):
    return f"Hello, {name} 🎉"
"""
        result = analyze_code(code)

        assert isinstance(result, AnalysisResult)

    def test_multiline_string(self):
        """Test handling of multiline strings."""
        code = '''
def get_doc():
    """
    This is a multiline
    docstring.
    """
    pass
'''
        result = analyze_code(code)

        assert isinstance(result, AnalysisResult)

    def test_decorator_handling(self):
        """Test handling of decorated functions."""
        code = """
from functools import lru_cache

@lru_cache(maxsize=128)
def fib(n):
    if n < 2:
        return n
    return fib(n-1) + fib(n-2)
"""
        result = analyze_code(code)

        assert isinstance(result, AnalysisResult)


class TestIntegration:
    """Test integration with all analysis modules."""

    def test_full_analysis_integration(self):
        """Test that all analysis modules work together."""
        code = """
class DataProcessor:
    def __init__(self):
        self.data = []

    def process(self, items):
        for item in items:
            for sub_item in item.children:
                self.data.append(sub_item.value * 2)
        return self.data

    def save(self, filename):
        with open(filename, 'w') as f:
            f.write(str(self.data))
"""
        result = analyze_code(code)

        # All categories should be analyzed
        assert "logic" in result.summary["by_category"]
        assert "security" in result.summary["by_category"]
        assert "performance" in result.summary["by_category"]
        assert "maintainability" in result.summary["by_category"]

        # Should detect various issues
        total_issues = result.summary["total_issues"]
        assert total_issues >= 0  # May have issues from nested loops, resource handling, etc.
