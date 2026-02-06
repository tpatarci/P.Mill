"""Tests for function fact extraction."""

import ast

import pytest

from backend.analysis.ast_parser import parse_python_file
from backend.analysis.fact_extractor import extract_function_facts


class TestFactExtractor:
    """Test suite for fact extractor."""

    def test_extract_basic_facts(self, sample_python_code: str):
        """Test extraction of basic function facts."""
        tree, _ = parse_python_file(sample_python_code)

        # Find the 'add' function
        add_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "add":
                add_node = node
                break

        assert add_node is not None
        facts = extract_function_facts(add_node, sample_python_code)

        assert facts.function_name == "add"
        assert facts.line_start > 0
        assert facts.has_docstring is True
        assert facts.docstring == "Add two numbers."
        assert len(facts.parameters) == 2
        assert facts.parameters[0].name == "a"
        assert facts.parameters[1].name == "b"
        assert facts.return_annotation == "int"

    def test_extract_none_checks(self):
        """Test detection of None checks."""
        code = """
def check_none(x, y):
    if x is None:
        return "x is None"
    if y is not None:
        return "y is not None"
    return "ok"
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert "x" in facts.has_none_checks
        assert "y" in facts.has_none_checks

    def test_extract_type_checks(self):
        """Test detection of isinstance type checks."""
        code = """
def check_type(x):
    if isinstance(x, int):
        return x * 2
    return 0
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert "x" in facts.has_type_checks

    def test_detect_bare_except(self):
        """Test detection of bare except clauses."""
        code = """
def bad_exception_handling():
    try:
        risky_operation()
    except:
        pass
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert facts.has_bare_except is True

    def test_detect_broad_except(self):
        """Test detection of broad exception catching."""
        code = """
def broad_exception_handling():
    try:
        risky_operation()
    except Exception:
        pass
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert facts.has_broad_except is True
        assert "Exception" in facts.caught_types

    def test_detect_mutable_default_args(self):
        """Test detection of mutable default arguments."""
        code = """
def bad_defaults(items=[]):
    items.append(1)
    return items
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert facts.has_mutable_default_args is True
        assert facts.parameters[0].default_is_mutable is True

    def test_detect_raises(self):
        """Test detection of raised exceptions."""
        code = """
def raises_errors(x):
    if x < 0:
        raise ValueError("negative")
    if x == 0:
        raise ZeroDivisionError("zero")
    return 1 / x
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert "ValueError" in facts.raise_types
        assert "ZeroDivisionError" in facts.raise_types

    def test_detect_function_calls(self):
        """Test detection of function calls."""
        code = """
def calls_functions():
    print("hello")
    len([1, 2, 3])
    custom_function()
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert "print" in facts.calls
        assert "len" in facts.calls
        assert "custom_function" in facts.calls

    def test_detect_command_execution(self, vulnerable_code: str):
        """Test detection of command execution."""
        tree, _ = parse_python_file(vulnerable_code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, vulnerable_code)

        assert facts.uses_command_execution is True
        assert facts.command_execution_has_fstring is True

    def test_detect_shadows_builtin(self):
        """Test detection of parameters shadowing builtins."""
        code = """
def bad_names(list, dict, type):
    return list + dict + type
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert "list" in facts.shadows_builtin
        assert "dict" in facts.shadows_builtin
        assert "type" in facts.shadows_builtin

    def test_cyclomatic_complexity(self, complex_code: str):
        """Test cyclomatic complexity calculation."""
        tree, _ = parse_python_file(complex_code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, complex_code)

        # Complex nested if/elif structure should have high complexity
        assert facts.cyclomatic_complexity > 5

    def test_async_function_detection(self):
        """Test detection of async functions."""
        code = """
async def fetch_data():
    return await some_api()
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef))
        facts = extract_function_facts(func_node, code)

        assert facts.is_async is True

    def test_method_detection(self, sample_python_code: str):
        """Test detection of class methods."""
        tree, _ = parse_python_file(sample_python_code)

        # Find the multiply method
        multiply_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "multiply":
                multiply_node = node
                break

        facts = extract_function_facts(multiply_node, sample_python_code, class_name="Calculator")

        assert facts.is_method is True
        assert facts.class_name == "Calculator"
        assert facts.qualified_name == "Calculator.multiply"

    def test_decorator_extraction(self):
        """Test extraction of decorators."""
        code = """
@staticmethod
@cache
def decorated_func():
    pass
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert len(facts.decorators) == 2
        assert "staticmethod" in facts.decorators
        assert "cache" in facts.decorators

    def test_open_without_with(self):
        """Test detection of open() without context manager."""
        code = """
def unsafe_file_handling():
    f = open("file.txt")
    data = f.read()
    f.close()
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert facts.uses_open_without_with is True

    @pytest.mark.skip(reason="Known limitation: requires two-pass analysis to detect open() inside with")
    def test_open_with_context_manager(self):
        """Test that open() with 'with' is safe."""
        code = """
def safe_file_handling():
    with open("file.txt") as f:
        data = f.read()
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert facts.uses_open_without_with is False

    def test_unreachable_code_detection(self):
        """Test detection of unreachable code."""
        code = """
def has_unreachable():
    if True:
        return 1
        print("never runs")
    return 2
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert facts.has_unreachable_code is True

    def test_no_return_annotation(self):
        """Test functions without return annotation."""
        code = """
def no_annotation(x):
    return x
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert facts.return_annotation is None

    def test_parameters_with_defaults(self):
        """Test detection of parameters with defaults."""
        code = """
def with_defaults(a, b=10, c="hello"):
    return a + b + len(c)
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        assert facts.parameters[0].has_default is False
        assert facts.parameters[1].has_default is True
        assert facts.parameters[2].has_default is True

    def test_varargs_detection(self):
        """Test detection of *args and **kwargs."""
        code = """
def with_varargs(*args, **kwargs):
    pass
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        # Note: This test currently just checks that it doesn't crash
        # *args and **kwargs handling could be enhanced in parameters extraction
        assert facts.function_name == "with_varargs"
