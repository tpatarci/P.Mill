"""AST parsing and function extraction for Python code."""

import ast
from typing import List, Optional

import structlog

from backend.models import FunctionInfo

logger = structlog.get_logger()

BUILTINS = {
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "callable",
    "chr", "classmethod", "compile", "complex", "delattr", "dict", "dir", "divmod",
    "enumerate", "eval", "exec", "filter", "float", "format", "frozenset", "getattr",
    "globals", "hasattr", "hash", "help", "hex", "id", "input", "int", "isinstance",
    "issubclass", "iter", "len", "list", "locals", "map", "max", "memoryview", "min",
    "next", "object", "oct", "open", "ord", "pow", "print", "property", "range",
    "repr", "reversed", "round", "set", "setattr", "slice", "sorted", "staticmethod",
    "str", "sum", "super", "tuple", "type", "vars", "zip"
}


class FunctionExtractor(ast.NodeVisitor):
    """Extract function definitions from Python AST."""

    def __init__(self, source_lines: List[str]):
        """Initialize extractor with source code lines."""
        self.source_lines = source_lines
        self.functions: List[FunctionInfo] = []
        self.current_class: Optional[str] = None
        self.class_stack: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class definition."""
        self.class_stack.append(node.name)
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit a regular function definition."""
        self._process_function(node, is_async=False)
        # Don't visit nested functions for MVP
        # self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit an async function definition."""
        self._process_function(node, is_async=True)
        # Don't visit nested functions for MVP
        # self.generic_visit(node)

    def _process_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
    ) -> None:
        """Process a function or method definition."""
        # Extract parameter names
        params = []
        for arg in node.args.args:
            params.append(arg.arg)
        if node.args.vararg:
            params.append(f"*{node.args.vararg.arg}")
        if node.args.kwonlyargs:
            params.extend(arg.arg for arg in node.args.kwonlyargs)
        if node.args.kwarg:
            params.append(f"**{node.args.kwarg.arg}")

        # Extract return type
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)

        # Extract docstring
        docstring = ast.get_docstring(node)

        # Get line range
        line_start = node.lineno
        line_end = node.end_lineno or line_start

        # Build function info
        func_info = FunctionInfo(
            name=node.name,
            line_start=line_start,
            line_end=line_end,
            parameters=params,
            return_type=return_type,
            docstring=docstring,
            complexity=0,  # Will be filled by radon in fact_extractor
        )

        self.functions.append(func_info)

        logger.debug(
            "function_extracted",
            name=node.name,
            is_async=is_async,
            is_method=self.current_class is not None,
            class_name=self.current_class,
            param_count=len(params),
            has_docstring=docstring is not None,
        )


def parse_python_file(source_code: str) -> tuple[ast.Module, List[FunctionInfo]]:
    """
    Parse Python source code and extract function inventory.

    Args:
        source_code: Python source code as string

    Returns:
        Tuple of (parsed AST, list of FunctionInfo)

    Raises:
        SyntaxError: If source code has syntax errors
    """
    try:
        tree = ast.parse(source_code)
        source_lines = source_code.splitlines()

        extractor = FunctionExtractor(source_lines)
        extractor.visit(tree)

        logger.info(
            "ast_parsing_complete",
            function_count=len(extractor.functions),
        )

        return tree, extractor.functions

    except SyntaxError as e:
        logger.error(
            "ast_parsing_failed",
            error=str(e),
            line=e.lineno,
            offset=e.offset,
        )
        raise


def get_function_source(
    source_code: str, line_start: int, line_end: int
) -> str:
    """
    Extract source code for a specific function by line range.

    Args:
        source_code: Full source code
        line_start: Starting line (1-indexed)
        line_end: Ending line (1-indexed)

    Returns:
        Function source code as string
    """
    lines = source_code.splitlines()
    # Convert to 0-indexed
    return "\n".join(lines[line_start - 1:line_end])


def get_function_ast_node(
    tree: ast.Module, function_name: str
) -> Optional[ast.FunctionDef | ast.AsyncFunctionDef]:
    """
    Find the AST node for a specific function by name.

    Args:
        tree: Parsed AST module
        function_name: Name of function to find

    Returns:
        Function AST node or None if not found
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                return node
    return None
