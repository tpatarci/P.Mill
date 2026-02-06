"""Tests for AST parser and function extraction."""

import ast

import pytest

from backend.analysis.ast_parser import (
    get_function_ast_node,
    get_function_source,
    parse_python_file,
)


class TestASTParser:
    """Test suite for AST parser."""

    def test_parse_sample_python_code(self, sample_python_code: str):
        """Test parsing sample Python code."""
        tree, functions = parse_python_file(sample_python_code)

        assert isinstance(tree, ast.Module)
        assert len(functions) == 4  # add, divide, __init__, multiply

        # Check function names
        names = [f.name for f in functions]
        assert "add" in names
        assert "divide" in names
        assert "__init__" in names
        assert "multiply" in names

    def test_function_parameters_extracted(self, sample_python_code: str):
        """Test that function parameters are extracted."""
        _, functions = parse_python_file(sample_python_code)

        add_func = next(f for f in functions if f.name == "add")
        assert add_func.parameters == ["a", "b"]

    def test_function_return_type_extracted(self, sample_python_code: str):
        """Test that return type annotations are extracted."""
        _, functions = parse_python_file(sample_python_code)

        add_func = next(f for f in functions if f.name == "add")
        assert add_func.return_type == "int"

        divide_func = next(f for f in functions if f.name == "divide")
        assert divide_func.return_type == "float"

    def test_function_docstring_extracted(self, sample_python_code: str):
        """Test that docstrings are extracted."""
        _, functions = parse_python_file(sample_python_code)

        add_func = next(f for f in functions if f.name == "add")
        assert add_func.docstring == "Add two numbers."

    def test_function_line_range_extracted(self, sample_python_code: str):
        """Test that line ranges are extracted."""
        _, functions = parse_python_file(sample_python_code)

        add_func = next(f for f in functions if f.name == "add")
        assert add_func.line_start > 0
        assert add_func.line_end >= add_func.line_start

    def test_parse_vulnerable_code(self, vulnerable_code: str):
        """Test parsing vulnerable code."""
        tree, functions = parse_python_file(vulnerable_code)

        assert isinstance(tree, ast.Module)
        assert len(functions) == 1

        func = functions[0]
        assert func.name == "execute_command"
        assert "user_input" in func.parameters

    def test_parse_complex_code(self, complex_code: str):
        """Test parsing complex nested code."""
        tree, functions = parse_python_file(complex_code)

        assert isinstance(tree, ast.Module)
        assert len(functions) == 1

        func = functions[0]
        assert func.name == "complex_function"
        assert func.parameters == ["x", "y", "z"]

    def test_parse_syntax_error(self):
        """Test handling of syntax errors."""
        bad_code = "def broken( syntax error"

        with pytest.raises(SyntaxError):
            parse_python_file(bad_code)

    def test_get_function_source(self, sample_python_code: str):
        """Test extracting function source code."""
        _, functions = parse_python_file(sample_python_code)

        add_func = next(f for f in functions if f.name == "add")
        source = get_function_source(
            sample_python_code, add_func.line_start, add_func.line_end
        )

        assert "def add" in source
        assert "return a + b" in source

    def test_get_function_ast_node(self, sample_python_code: str):
        """Test finding AST node by function name."""
        tree, _ = parse_python_file(sample_python_code)

        node = get_function_ast_node(tree, "add")
        assert node is not None
        assert isinstance(node, ast.FunctionDef)
        assert node.name == "add"

    def test_get_function_ast_node_not_found(self, sample_python_code: str):
        """Test handling of function not found."""
        tree, _ = parse_python_file(sample_python_code)

        node = get_function_ast_node(tree, "nonexistent")
        assert node is None

    def test_async_function_detection(self):
        """Test detection of async functions."""
        code = """
async def fetch_data():
    return await some_api()
"""
        tree, functions = parse_python_file(code)

        assert len(functions) == 1
        func = functions[0]
        assert func.name == "fetch_data"

    def test_method_extraction_from_class(self, sample_python_code: str):
        """Test that methods are extracted from classes."""
        _, functions = parse_python_file(sample_python_code)

        multiply_func = next(f for f in functions if f.name == "multiply")
        assert multiply_func is not None
        assert "self" in multiply_func.parameters

    def test_varargs_extraction(self):
        """Test extraction of *args and **kwargs."""
        code = """
def func(a, *args, b=1, **kwargs):
    pass
"""
        _, functions = parse_python_file(code)

        func = functions[0]
        assert "a" in func.parameters
        assert "*args" in func.parameters
        assert "b" in func.parameters
        assert "**kwargs" in func.parameters

    def test_no_return_annotation(self):
        """Test functions without return type annotation."""
        code = """
def no_annotation(x):
    return x
"""
        _, functions = parse_python_file(code)

        func = functions[0]
        assert func.return_type is None

    def test_empty_file(self):
        """Test parsing empty file."""
        code = ""
        tree, functions = parse_python_file(code)

        assert isinstance(tree, ast.Module)
        assert len(functions) == 0

    def test_no_functions(self):
        """Test parsing file with no functions."""
        code = """
x = 1
y = 2
print(x + y)
"""
        tree, functions = parse_python_file(code)

        assert isinstance(tree, ast.Module)
        assert len(functions) == 0
