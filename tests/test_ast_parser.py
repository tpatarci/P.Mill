"""Tests for AST parser and function extraction."""

import ast

import pytest

from backend.analysis.ast_parser import (
    ASTNodeBuilder,
    BUILTINS,
    build_code_structure,
    get_function_ast_node,
    get_function_source,
    parse_python_file,
)
from backend.models import ASTNode, ClassInfo, CodeStructure, ImportInfo


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


class TestClassExtraction:
    """Test suite for class extraction."""

    def test_extract_class_with_methods(self):
        """Test extracting a class with methods."""
        code = """
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
"""
        structure = build_code_structure(code)

        assert len(structure.classes) == 1
        cls = structure.classes[0]
        assert cls.name == "Calculator"
        assert "add" in cls.methods
        assert "subtract" in cls.methods
        assert cls.line_start == 2
        assert cls.line_end >= 6

    def test_extract_class_with_bases(self):
        """Test extracting class with inheritance."""
        code = """
class Dog(Animal):
    pass

class Cat(Animal, Pet):
    pass
"""
        structure = build_code_structure(code)

        assert len(structure.classes) == 2

        dog = next(c for c in structure.classes if c.name == "Dog")
        assert dog.bases == ["Animal"]

        cat = next(c for c in structure.classes if c.name == "Cat")
        assert cat.bases == ["Animal", "Pet"]

    def test_extract_class_with_decorators(self):
        """Test extracting class with decorators."""
        code = """
@dataclass
class Point:
    x: int
    y: int
"""
        structure = build_code_structure(code)

        assert len(structure.classes) == 1
        cls = structure.classes[0]
        assert "dataclass" in cls.decorators

    def test_extract_class_with_docstring(self):
        """Test extracting class docstring."""
        code = """
class MyClass:
    '''A class for testing.'''
    pass
"""
        structure = build_code_structure(code)

        assert len(structure.classes) == 1
        cls = structure.classes[0]
        assert cls.docstring == "A class for testing."

    def test_extract_nested_class(self):
        """Test that nested classes are extracted."""
        code = """
class Outer:
    class Inner:
        pass
"""
        structure = build_code_structure(code)

        # Should extract both classes
        assert len(structure.classes) == 2
        names = [c.name for c in structure.classes]
        assert "Outer" in names
        assert "Inner" in names


class TestImportExtraction:
    """Test suite for import extraction."""

    def test_extract_import(self):
        """Test extracting simple import."""
        code = """
import os
import sys
"""
        structure = build_code_structure(code)

        assert len(structure.imports) == 2

        os_import = next(i for i in structure.imports if i.module == "os")
        assert os_import.line == 2
        assert os_import.is_from is False

    def test_extract_import_with_alias(self):
        """Test extracting import with alias."""
        code = """
import numpy as np
"""
        structure = build_code_structure(code)

        assert len(structure.imports) == 1
        imp = structure.imports[0]
        assert imp.module == "numpy"
        assert imp.alias == "np"

    def test_extract_from_import(self):
        """Test extracting 'from' import."""
        code = """
from os.path import join
"""
        structure = build_code_structure(code)

        assert len(structure.imports) == 1
        imp = structure.imports[0]
        assert imp.module == "os.path"
        assert imp.names == ["join"]
        assert imp.is_from is True

    def test_extract_from_import_multiple(self):
        """Test extracting 'from' import with multiple names."""
        code = """
from os import path, environ
"""
        structure = build_code_structure(code)

        assert len(structure.imports) == 1
        imp = structure.imports[0]
        assert imp.names == ["path", "environ"]

    def test_extract_from_import_star(self):
        """Test extracting star import."""
        code = """
from os import *
"""
        structure = build_code_structure(code)

        assert len(structure.imports) == 1
        imp = structure.imports[0]
        assert imp.names == ["*"]

    def test_extract_relative_import(self):
        """Test extracting relative import."""
        code = """
from .local_module import func
"""
        structure = build_code_structure(code)

        assert len(structure.imports) == 1
        imp = structure.imports[0]
        # The module for relative imports is the full path including level
        assert imp.names == ["func"]
        assert imp.is_from is True
        # The module attribute stores the relative path
        assert imp.module == "local_module"


class TestASTNodeBuilder:
    """Test suite for unified ASTNode tree building."""

    def test_build_module_node(self):
        """Test building root module node."""
        code = "x = 1\n"
        builder = ASTNodeBuilder(code)
        tree = ast.parse(code)
        root = builder.build(tree)

        assert root.node_type == "module"
        assert root.line_start == 1
        assert root.line_end == 1

    def test_build_function_node(self):
        """Test building function node."""
        code = """
def foo():
    pass
"""
        structure = build_code_structure(code)

        assert structure.ast.node_type == "module"
        assert len(structure.ast.children) > 0

        func_node = structure.ast.children[0]
        assert func_node.node_type == "function_def"
        assert func_node.name == "foo"

    def test_build_class_node(self):
        """Test building class node."""
        code = """
class MyClass:
    pass
"""
        structure = build_code_structure(code)

        class_node = structure.ast.children[0]
        assert class_node.node_type == "class_def"
        assert class_node.name == "MyClass"

    def test_build_if_statement(self):
        """Test building if statement node."""
        code = """
if x > 0:
    print("positive")
else:
    print("non-positive")
"""
        structure = build_code_structure(code)

        if_node = structure.ast.children[0]
        assert if_node.node_type == "if_stmt"
        assert if_node.attributes["has_else"] is True

    def test_build_for_loop(self):
        """Test building for loop node."""
        code = """
for item in items:
    process(item)
"""
        structure = build_code_structure(code)

        for_node = structure.ast.children[0]
        assert for_node.node_type == "for_loop"
        assert "target" in for_node.attributes
        assert "iter" in for_node.attributes

    def test_build_while_loop(self):
        """Test building while loop node."""
        code = """
while condition:
    do_something()
"""
        structure = build_code_structure(code)

        while_node = structure.ast.children[0]
        assert while_node.node_type == "while_loop"

    def test_build_try_statement(self):
        """Test building try statement node."""
        code = """
try:
    risky_operation()
except ValueError:
    handle_error
finally:
    cleanup()
"""
        structure = build_code_structure(code)

        try_node = structure.ast.children[0]
        assert try_node.node_type == "try_stmt"
        assert try_node.attributes["handlers"] == 1
        assert try_node.attributes["has_finally"] is True

    def test_build_with_statement(self):
        """Test building with statement node."""
        code = """
with open("file.txt") as f:
    content = f.read()
"""
        structure = build_code_structure(code)

        with_node = structure.ast.children[0]
        assert with_node.node_type == "with_stmt"
        assert "items" in with_node.attributes

    def test_build_return_statement(self):
        """Test building return statement node."""
        code = """
def foo():
    return 42
"""
        structure = build_code_structure(code)

        # Navigate to return statement (module -> function -> return)
        func_node = structure.ast.children[0]
        return_node = func_node.children[0]
        assert return_node.node_type == "return_stmt"
        assert "value" in return_node.attributes

    def test_build_import_nodes(self):
        """Test building import nodes."""
        code = """
import os
from sys import argv
"""
        structure = build_code_structure(code)

        import_nodes = [c for c in structure.ast.children if c.node_type == "import"]
        assert len(import_nodes) == 1

        from_nodes = [c for c in structure.ast.children if c.node_type == "import_from"]
        assert len(from_nodes) == 1

    def test_build_nested_structure(self):
        """Test building nested AST nodes."""
        code = """
class MyClass:
    def method(self):
        if True:
            return self.value
"""
        structure = build_code_structure(code)

        # Module -> Class -> Function -> If -> Return
        class_node = structure.ast.children[0]
        assert class_node.node_type == "class_def"
        assert len(class_node.children) > 0

        method_node = class_node.children[0]
        assert method_node.node_type == "function_def"
        assert len(method_node.children) > 0

        if_node = method_node.children[0]
        assert if_node.node_type == "if_stmt"
        assert len(if_node.children) > 0

        return_node = if_node.children[0]
        assert return_node.node_type == "return_stmt"

    def test_build_async_function(self):
        """Test building async function node."""
        code = """
async def fetch():
    return await api_call()
"""
        structure = build_code_structure(code)

        func_node = structure.ast.children[0]
        assert func_node.node_type == "async_function_def"
        assert func_node.attributes["async"] is True

    def test_build_comprehension(self):
        """Test building comprehension nodes."""
        code = """
result = [x * 2 for x in items]
"""
        structure = build_code_structure(code)

        assign_node = structure.ast.children[0]
        # The comprehension is nested inside the assign
        assert assign_node.node_type == "assign"


class TestBuildCodeStructure:
    """Test suite for complete CodeStructure building."""

    def test_build_complete_structure(self):
        """Test building complete CodeStructure."""
        code = '''
"""
A module for calculations.
"""

import os
from typing import List

class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

def multiply(x: int, y: int) -> int:
    """Multiply two numbers."""
    return x * y
'''
        structure = build_code_structure(code)

        # Check AST root
        assert structure.ast.node_type == "module"

        # Check functions
        assert len(structure.functions) == 2
        func_names = [f.name for f in structure.functions]
        assert "add" in func_names
        assert "multiply" in func_names

        # Check classes
        assert len(structure.classes) == 1
        assert structure.classes[0].name == "Calculator"
        assert structure.classes[0].docstring == "A simple calculator."

        # Check imports
        assert len(structure.imports) == 2
        import_names = [i.module for i in structure.imports]
        assert "os" in import_names
        assert "typing" in import_names

        # Check metrics
        assert structure.complexity_metrics.lines_of_code > 0

    def test_build_structure_with_syntax_error(self):
        """Test that syntax errors are raised."""
        code = "def broken(\n"

        with pytest.raises(SyntaxError):
            build_code_structure(code)

    def test_build_structure_empty_file(self):
        """Test building structure from empty file."""
        code = ""
        structure = build_code_structure(code)

        assert structure.ast.node_type == "module"
        assert len(structure.functions) == 0
        assert len(structure.classes) == 0
        assert len(structure.imports) == 0

    def test_build_structure_preserves_original_function(self):
        """Test that parse_python_file still works as before."""
        code = """
def test_func():
    pass
"""
        # Original function should still work
        tree, functions = parse_python_file(code)

        assert isinstance(tree, ast.Module)
        assert len(functions) == 1
        assert functions[0].name == "test_func"

        # New function should also work
        structure = build_code_structure(code)

        assert len(structure.functions) == 1
        assert structure.functions[0].name == "test_func"
