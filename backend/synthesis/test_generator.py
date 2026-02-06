"""Test generation for functions.

This module generates:
- Unit tests based on function signatures
- Edge case tests
- Property-based tests
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional

import structlog

from backend.models import FunctionInfo

logger = structlog.get_logger()


@dataclass
class GeneratedTest:
    """A generated test case."""

    test_name: str
    function_name: str
    test_code: str
    test_type: str  # "unit", "edge_case", "property"
    description: str


class TestGenerator(ast.NodeVisitor):
    """Generate tests for functions."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.generated_tests: List[GeneratedTest] = []
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        # Extract function info
        func_name = node.name
        full_name = f"{self.current_class}.{func_name}" if self.current_class else func_name

        # Generate unit tests
        self._generate_unit_test(node, full_name)

        # Generate edge case tests
        self._generate_edge_case_tests(node, full_name)

        # Generate property-based tests
        self._generate_property_tests(node, full_name)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self.visit_FunctionDef(node)

    def _generate_unit_test(self, node: ast.FunctionDef, full_name: str) -> None:
        """Generate a basic unit test."""
        func_name = node.name
        params = [arg.arg for arg in node.args.args if arg.arg not in ["self", "cls"]]

        # Build test function
        test_name = f"test_{func_name}"

        # Generate test arguments
        if params:
            args = ", ".join(params)
            args_comment = f"# TODO: Provide test values for: {', '.join(params)}"
        else:
            args = ""
            args_comment = ""

        # Handle async functions
        is_async = isinstance(node, ast.AsyncFunctionDef)

        test_code = f"""def {test_name}():
    '''Test {func_name} behavior.'''
    {args_comment}
    result = {full_name}({args})
    assert result is not None
"""

        if is_async:
            test_code = f"""async def {test_name}():
    '''Test {func_name} behavior.'''
    {args_comment}
    result = await {full_name}({args})
    assert result is not None
"""

        self.generated_tests.append(
            GeneratedTest(
                test_name=test_name,
                function_name=full_name,
                test_code=test_code,
                test_type="unit",
                description=f"Unit test for {full_name}",
            )
        )

    def _generate_edge_case_tests(self, node: ast.FunctionDef, full_name: str) -> None:
        """Generate edge case tests."""
        func_name = node.name
        params = [arg.arg for arg in node.args.args if arg.arg not in ["self", "cls"]]

        # Check for Optional parameters
        for arg in node.args.args:
            if arg.annotation:
                annotation = ast.unparse(arg.annotation)
                if "Optional" in annotation or "Union" in annotation or "|" in annotation:
                    param_name = arg.arg
                    test_name = f"test_{func_name}_with_none_{param_name}"

                    test_code = f"""def {test_name}():
    '''Test {func_name} with None for {param_name}.'''
    # TODO: Verify None handling for parameter {param_name}
    result = {full_name}({param_name}=None)
    # Check if function handles None appropriately
"""

                    self.generated_tests.append(
                        GeneratedTest(
                            test_name=test_name,
                            function_name=full_name,
                            test_code=test_code,
                            test_type="edge_case",
                            description=f"Edge case test for None parameter {param_name}",
                        )
                    )

        # Generate empty collection tests for functions with list/dict params
        for arg in node.args.args:
            if arg.annotation:
                annotation = ast.unparse(arg.annotation)
                if "List" in annotation or "list" in annotation:
                    param_name = arg.arg
                    test_name = f"test_{func_name}_with_empty_{param_name}"

                    test_code = f"""def {test_name}():
    '''Test {func_name} with empty list.'''
    result = {full_name}({param_name}=[])
    # Verify behavior with empty list
"""

                    self.generated_tests.append(
                        GeneratedTest(
                            test_name=test_name,
                            function_name=full_name,
                            test_code=test_code,
                            test_type="edge_case",
                            description=f"Edge case test for empty list {param_name}",
                        )
                    )

    def _generate_property_tests(self, node: ast.FunctionDef, full_name: str) -> None:
        """Generate property-based tests."""
        func_name = node.name

        # Only generate for functions with return annotations
        if not node.returns:
            return

        return_type = ast.unparse(node.returns)

        # Generate property tests for pure functions
        if "List" in return_type or "list" in return_type:
            test_name = f"test_{func_name}_returns_list"

            test_code = f"""def {test_name}():
    '''Test that {func_name} returns a list.'''
    import pytest
    result = {full_name}()
    assert isinstance(result, list)
"""

            self.generated_tests.append(
                GeneratedTest(
                    test_name=test_name,
                    function_name=full_name,
                    test_code=test_code,
                    test_type="property",
                    description=f"Property test for list return type",
                )
            )


def generate_tests(
    source_code: str,
    functions: List[FunctionInfo],
) -> List[GeneratedTest]:
    """
    Generate tests for functions.

    Args:
        source_code: Python source code
        functions: List of functions to generate tests for

    Returns:
        List of GeneratedTest objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    generator = TestGenerator(source_code)
    generator.visit(tree)

    return generator.generated_tests


def generate_test_file(tests: List[GeneratedTest], module_name: str = "module") -> str:
    """
    Generate a complete test file.

    Args:
        tests: List of generated tests
        module_name: Name of the module being tested

    Returns:
        Complete test file content
    """
    header = f'''"""Tests for {module_name}.

Generated by P.Mill Test Generator.
TODO: Review and complete test implementations.
"""

import pytest
'''

    test_functions = "\n\n".join(test.test_code for test in tests)

    return header + "\n\n" + test_functions


def generate_test_report(tests: List[GeneratedTest]) -> dict:
    """
    Generate test generation report.

    Args:
        tests: List of generated tests

    Returns:
        Dict with summary and details
    """
    return {
        "summary": {
            "total_tests": len(tests),
            "by_type": {
                "unit": len([t for t in tests if t.test_type == "unit"]),
                "edge_case": len([t for t in tests if t.test_type == "edge_case"]),
                "property": len([t for t in tests if t.test_type == "property"]),
            },
        },
        "tests": [
            {
                "name": test.test_name,
                "function": test.function_name,
                "type": test.test_type,
                "description": test.description,
            }
            for test in tests
        ],
    }
