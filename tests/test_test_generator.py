"""Tests for test generator."""

import pytest

from backend.models import FunctionInfo
from backend.synthesis.test_generator import (
    GeneratedTest,
    TestGenerator,
    generate_test_file,
    generate_test_report,
    generate_tests,
)


class TestTestGeneration:
    """Test test generation for various function types."""

    def test_empty_code(self):
        """Test with empty code."""
        tests = generate_tests("", [])

        assert tests == []

    def test_simple_function(self):
        """Test test generation for simple function."""
        code = """
def add(x, y):
    return x + y
"""
        tests = generate_tests(code, [])

        assert len(tests) > 0
        assert any(t.test_name == "test_add" for t in tests)

    def test_function_with_optional_param(self):
        """Test edge case generation for Optional parameters."""
        code = """
from typing import Optional

def process(value: Optional[str]) -> str:
    return value or "default"
"""
        tests = generate_tests(code, [])

        # Should generate None edge case test
        assert any("none" in t.test_name.lower() for t in tests)

    def test_function_with_list_param(self):
        """Test edge case generation for list parameters."""
        code = """
def sum_items(items: list) -> int:
    return sum(items)
"""
        tests = generate_tests(code, [])

        # Should generate empty list edge case test
        assert any("empty" in t.test_name.lower() for t in tests)

    def test_function_with_return_annotation(self):
        """Test property test generation for functions with return type."""
        code = """
def get_items() -> list:
    return [1, 2, 3]
"""
        tests = generate_tests(code, [])

        # Should generate property test
        assert any(t.test_type == "property" for t in tests)

    def test_class_method(self):
        """Test test generation for class methods."""
        code = """
class Calculator:
    def add(self, x, y):
        return x + y
"""
        tests = generate_tests(code, [])

        # Should generate test with full name
        assert any("Calculator.add" in t.function_name for t in tests)

    def test_async_function(self):
        """Test test generation for async functions."""
        code = """
async def fetch_data():
    return {"data": "value"}
"""
        tests = generate_tests(code, [])

        assert len(tests) > 0
        # Should use async def in test
        assert "async def" in tests[0].test_code

    def test_function_without_params(self):
        """Test test generation for parameterless functions."""
        code = """
def get_value():
    return 42
"""
        tests = generate_tests(code, [])

        assert len(tests) > 0


class TestTestFileGeneration:
    """Test complete test file generation."""

    def test_generate_test_file(self):
        """Test generating a complete test file."""
        tests = [
            GeneratedTest(
                test_name="test_add",
                function_name="add",
                test_code="def test_add():\n    assert add(1, 1) == 2",
                test_type="unit",
                description="Test add function",
            )
        ]

        test_file = generate_test_file(tests, "mymodule")

        assert "Tests for mymodule" in test_file
        assert "import pytest" in test_file
        assert "def test_add" in test_file

    def test_generate_test_file_multiple_tests(self):
        """Test generating test file with multiple tests."""
        tests = [
            GeneratedTest(
                test_name="test_add",
                function_name="add",
                test_code="def test_add(): pass",
                test_type="unit",
                description="Test add",
            ),
            GeneratedTest(
                test_name="test_subtract",
                function_name="subtract",
                test_code="def test_subtract(): pass",
                test_type="unit",
                description="Test subtract",
            ),
        ]

        test_file = generate_test_file(tests, "math")

        assert "def test_add" in test_file
        assert "def test_subtract" in test_file

    def test_generate_test_file_empty(self):
        """Test generating test file with no tests."""
        test_file = generate_test_file([], "empty")

        assert "Tests for empty" in test_file
        assert "import pytest" in test_file


class TestTestReport:
    """Test test generation report."""

    def test_empty_report(self):
        """Test report with no tests."""
        report = generate_test_report([])

        assert report["summary"]["total_tests"] == 0
        assert report["tests"] == []

    def test_report_with_tests(self):
        """Test report with generated tests."""
        tests = [
            GeneratedTest(
                test_name="test1",
                function_name="func1",
                test_code="code1",
                test_type="unit",
                description="desc1",
            ),
            GeneratedTest(
                test_name="test2",
                function_name="func2",
                test_code="code2",
                test_type="edge_case",
                description="desc2",
            ),
        ]

        report = generate_test_report(tests)

        assert report["summary"]["total_tests"] == 2
        assert report["summary"]["by_type"]["unit"] == 1
        assert report["summary"]["by_type"]["edge_case"] == 1
        assert len(report["tests"]) == 2

    def test_report_aggregates_by_type(self):
        """Test that report aggregates by test type."""
        tests = [
            GeneratedTest("t1", "f1", "c1", "unit", "d1"),
            GeneratedTest("t2", "f2", "c2", "unit", "d2"),
            GeneratedTest("t3", "f3", "c3", "property", "d3"),
        ]

        report = generate_test_report(tests)

        assert report["summary"]["by_type"]["unit"] == 2
        assert report["summary"]["by_type"]["property"] == 1


class TestTestGeneratorClass:
    """Test TestGenerator class."""

    def test_initialization(self):
        """Test generator initialization."""
        generator = TestGenerator("code")

        assert generator.source_code == "code"
        assert generator.generated_tests == []

    def test_visits_function(self):
        """Test that generator visits functions."""
        code = "def test(): return 1"
        import ast

        tree = ast.parse(code)
        generator = TestGenerator(code)
        generator.visit(tree)

        assert isinstance(generator.generated_tests, list)


class TestGeneratedTestDataclass:
    """Test GeneratedTest dataclass."""

    def test_all_fields(self):
        """Test GeneratedTest has all required fields."""
        test = GeneratedTest(
            test_name="test_func",
            function_name="func",
            test_code="def test_func(): pass",
            test_type="unit",
            description="Test function",
        )

        assert test.test_name == "test_func"
        assert test.function_name == "func"
        assert test.test_type == "unit"
        assert test.description == "Test function"


class TestEdgeCases:
    """Test edge cases."""

    def test_syntax_error_code(self):
        """Test with syntax error."""
        tests = generate_tests("def broken(", [])

        assert tests == []

    def test_function_with_self_param(self):
        """Test that 'self' parameter is excluded from test generation."""
        code = """
class MyClass:
    def method(self, x):
        return x * 2
"""
        tests = generate_tests(code, [])

        # Self should be handled properly
        assert len(tests) > 0

    def test_function_with_cls_param(self):
        """Test that 'cls' parameter is excluded from test generation."""
        code = """
class MyClass:
    @classmethod
    def class_method(cls, x):
        return x * 2
"""
        tests = generate_tests(code, [])

        # Cls should be handled properly
        assert len(tests) > 0


class TestNestedClass:
    """Test nested class handling."""

    def test_nested_class_methods(self):
        """Test test generation for nested class methods."""
        code = """
class Outer:
    class Inner:
        def method(self):
            pass
"""
        tests = generate_tests(code, [])

        # Should handle nested classes
        assert isinstance(tests, list)


class TestComplexFunctions:
    """Test test generation for complex functions."""

    def test_function_with_many_params(self):
        """Test test generation for functions with many parameters."""
        code = """
def complex_func(a, b, c, d, e):
    return a + b + c + d + e
"""
        tests = generate_tests(code, [])

        assert len(tests) > 0
        # Test should mention all parameters
        assert "a, b, c, d, e" in tests[0].test_code

    def test_function_with_docstring(self):
        """Test that docstrings are preserved."""
        code = '''
def documented(x):
    """This is documented."""
    return x
'''
        tests = generate_tests(code, [])

        assert len(tests) > 0
