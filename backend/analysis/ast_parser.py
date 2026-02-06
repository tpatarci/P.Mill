"""AST parsing and structure extraction for Python code."""

import ast
from typing import Any, Dict, List, Optional

import structlog

from backend.models import (
    ASTNode,
    ClassInfo,
    CodeStructure,
    ComplexityMetrics,
    FunctionInfo,
    ImportInfo,
)

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


class ClassExtractor(ast.NodeVisitor):
    """Extract class definitions from Python AST."""

    def __init__(self):
        """Initialize class extractor."""
        self.classes: List[ClassInfo] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class definition and extract its info."""
        # Extract base class names
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(ast.unparse(base))
            elif isinstance(base, ast.Subscript):
                bases.append(ast.unparse(base))

        # Extract method names
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)

        # Extract decorators
        decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                decorators.append(ast.unparse(decorator))
            elif isinstance(decorator, ast.Call):
                decorators.append(ast.unparse(decorator.func))
            else:
                decorators.append(ast.unparse(decorator))

        # Extract docstring
        docstring = ast.get_docstring(node)

        class_info = ClassInfo(
            name=node.name,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            methods=methods,
            bases=bases,
            decorators=decorators,
            docstring=docstring,
        )

        self.classes.append(class_info)

        logger.debug(
            "class_extracted",
            name=node.name,
            method_count=len(methods),
            base_count=len(bases),
            decorator_count=len(decorators),
        )

        # Continue visiting to extract nested classes
        self.generic_visit(node)


class ImportExtractor(ast.NodeVisitor):
    """Extract import statements from Python AST."""

    def __init__(self):
        """Initialize import extractor."""
        self.imports: List[ImportInfo] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Visit an import statement."""
        for alias in node.names:
            import_info = ImportInfo(
                module=alias.name,
                names=[],
                alias=alias.asname,
                line=node.lineno,
                is_from=False,
            )
            self.imports.append(import_info)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit a 'from ... import ...' statement."""
        module = node.module or ""
        names = []
        alias = None

        for alias_node in node.names:
            names.append(alias_node.name)
            if alias_node.asname:
                alias = alias_node.asname

        import_info = ImportInfo(
            module=module,
            names=names,
            alias=alias,
            line=node.lineno,
            is_from=True,
        )
        self.imports.append(import_info)


class ASTNodeBuilder(ast.NodeVisitor):
    """Build a unified ASTNode tree from Python AST."""

    def __init__(self, source_code: str):
        """Initialize builder with source code."""
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.root: Optional[ASTNode] = None

    def build(self, tree: ast.Module) -> ASTNode:
        """
        Build the ASTNode tree from an AST module.

        Args:
            tree: Parsed AST module

        Returns:
            Root ASTNode representing the entire module
        """
        # Count lines for line_end
        line_end = len(self.source_lines)

        # Create root module node
        self.root = ASTNode(
            node_type="module",
            name=None,
            line_start=1,
            line_end=line_end,
            children=[],
            attributes={"body_count": len(tree.body)},
        )

        # Process each top-level statement
        for node in tree.body:
            child_node = self._build_node(node)
            if child_node:
                self.root.children.append(child_node)

        return self.root

    def _build_node(self, node: ast.AST, parent: Optional[ASTNode] = None) -> Optional[ASTNode]:
        """
        Build an ASTNode from an AST node.

        Args:
            node: AST node to convert
            parent: Parent ASTNode (for context)

        Returns:
            ASTNode or None if node type is not handled
        """
        if node is None:
            return None

        # Get line range
        line_start = getattr(node, "lineno", 1)
        line_end = getattr(node, "end_lineno", line_start)

        # Determine node type and build accordingly
        node_type = self._get_node_type(node)
        if node_type is None:
            return None

        # Get name if applicable
        name = self._get_node_name(node)

        # Extract attributes
        attributes = self._extract_attributes(node)

        # Create ASTNode
        ast_node = ASTNode(
            node_type=node_type,
            name=name,
            line_start=line_start,
            line_end=line_end,
            children=[],
            attributes=attributes,
        )

        # Add children for compound statements
        children = self._get_child_nodes(node)
        for child in children:
            child_ast_node = self._build_node(child, ast_node)
            if child_ast_node:
                ast_node.children.append(child_ast_node)

        return ast_node

    def _get_node_type(self, node: ast.AST) -> Optional[str]:
        """Get the node type string for an AST node."""
        type_map = {
            # Module
            ast.Module: "module",

            # Definitions
            ast.FunctionDef: "function_def",
            ast.AsyncFunctionDef: "async_function_def",
            ast.ClassDef: "class_def",

            # Imports
            ast.Import: "import",
            ast.ImportFrom: "import_from",

            # Control flow
            ast.If: "if_stmt",
            ast.For: "for_loop",
            ast.AsyncFor: "async_for_loop",
            ast.While: "while_loop",
            ast.Break: "break_stmt",
            ast.Continue: "continue_stmt",
            ast.Return: "return_stmt",
            ast.Yield: "yield_stmt",
            ast.YieldFrom: "yield_from_stmt",

            # Exceptions
            ast.Try: "try_stmt",
            ast.ExceptHandler: "except_handler",
            ast.Raise: "raise_stmt",

            # Variables
            ast.Assign: "assign",
            ast.AugAssign: "aug_assign",
            ast.AnnAssign: "annotated_assign",
            ast.NamedExpr: "named_expr",  # Walrus operator
            ast.Global: "global_stmt",
            ast.Nonlocal: "nonlocal_stmt",

            # Expressions
            ast.Expr: "expr_stmt",
            ast.Pass: "pass_stmt",
            ast.Delete: "delete_stmt",
            ast.Assert: "assert_stmt",

            # Async
            ast.AsyncWith: "async_with",
            ast.AsyncFor: "async_for_loop",

            # Context managers
            ast.With: "with_stmt",

            # Loops
            ast.For: "for_loop",

            # Other statements
            ast.Lambda: "lambda",
            ast.IfExp: "if_exp",  # Ternary
            ast.JoinedStr: "joined_str",  # f-string
            ast.FormattedValue: "formatted_value",

            # Comprehensions
            ast.ListComp: "list_comp",
            ast.SetComp: "set_comp",
            ast.DictComp: "dict_comp",
            ast.GeneratorExp: "generator_exp",
            ast.comprehension: "comprehension",

            # Await
            ast.Await: "await",

            # Star/kwargs
            ast.Starred: "starred",
        }

        return type_map.get(type(node))

    def _get_node_name(self, node: ast.AST) -> Optional[str]:
        """Get the name for an AST node if applicable."""
        # Direct name attribute
        if hasattr(node, "name"):
            return getattr(node, "name")

        # For function calls, get the function name
        if isinstance(node, (ast.Call, ast.Attribute)):
            return ast.unparse(node)

        # For assignments with a single target
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                return target.id
            elif isinstance(target, ast.Attribute):
                return ast.unparse(target)

        return None

    def _extract_attributes(self, node: ast.AST) -> Dict[str, Any]:
        """Extract relevant attributes from an AST node."""
        attrs = {}

        # For function/class definitions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            attrs["async"] = isinstance(node, ast.AsyncFunctionDef)
            if node.returns:
                attrs["return_type"] = ast.unparse(node.returns)
            attrs["args"] = [arg.arg for arg in node.args.args]
            attrs["vararg"] = node.args.vararg.arg if node.args.vararg else None
            attrs["kwarg"] = node.args.kwarg.arg if node.args.kwarg else None
            attrs["decorator_list"] = [ast.unparse(d) for d in node.decorator_list]

        elif isinstance(node, ast.ClassDef):
            attrs["bases"] = [ast.unparse(b) for b in node.bases]
            attrs["decorator_list"] = [ast.unparse(d) for d in node.decorator_list]

        # For imports
        elif isinstance(node, ast.Import):
            attrs["names"] = [(alias.name, alias.asname) for alias in node.names]

        elif isinstance(node, ast.ImportFrom):
            attrs["module"] = node.module
            attrs["level"] = node.level
            attrs["names"] = [(alias.name, alias.asname) for alias in node.names]

        # For control flow
        elif isinstance(node, ast.If):
            attrs["has_else"] = node.orelse is not None
            attrs["test"] = ast.unparse(node.test) if hasattr(node.test, "unparse") else str(node.test)

        elif isinstance(node, (ast.For, ast.AsyncFor)):
            attrs["async"] = isinstance(node, ast.AsyncFor)
            attrs["has_else"] = node.orelse is not None
            attrs["target"] = ast.unparse(node.target) if hasattr(node.target, "unparse") else str(node.target)
            attrs["iter"] = ast.unparse(node.iter) if hasattr(node.iter, "unparse") else str(node.iter)

        elif isinstance(node, ast.While):
            attrs["has_else"] = node.orelse is not None

        elif isinstance(node, ast.Try):
            attrs["handlers"] = len(node.handlers)
            attrs["has_else"] = node.orelse is not None
            attrs["has_finally"] = node.finalbody is not None

        # For return/yield
        elif isinstance(node, ast.Return):
            if node.value:
                attrs["value"] = ast.unparse(node.value) if hasattr(node.value, "unparse") else str(node.value)

        # For with statements
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            attrs["async"] = isinstance(node, ast.AsyncWith)
            attrs["items"] = [
                (ast.unparse(item.context_expr), ast.unparse(item.optional_vars) if item.optional_vars else None)
                for item in node.items
            ]

        # For assignments
        elif isinstance(node, ast.Assign):
            attrs["targets"] = [ast.unparse(t) for t in node.targets]
            if node.value:
                attrs["value"] = ast.unparse(node.value) if hasattr(node.value, "unparse") else str(node.value)

        return attrs

    def _get_child_nodes(self, node: ast.AST) -> List[ast.AST]:
        """Get child nodes for an AST node."""
        children = []

        # For compound statements, get body content
        if hasattr(node, "body"):
            body = node.body
            if isinstance(body, list):
                children.extend(body)
            else:
                children.append(body)

        # For orelse blocks
        if hasattr(node, "orelse") and node.orelse:
            orelse = node.orelse
            if isinstance(orelse, list):
                children.extend(orelse)
            else:
                children.append(orelse)

        # For finalbody in try statements
        if hasattr(node, "finalbody") and node.finalbody:
            children.extend(node.finalbody)

        # For exception handlers
        if isinstance(node, ast.Try):
            children.extend(node.handlers)

        # For with items
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars:
                    children.append(item.optional_vars)

        # For loop target
        if isinstance(node, (ast.For, ast.AsyncFor)):
            if node.target:
                children.append(node.target)

        # For if test
        if isinstance(node, ast.If):
            if node.test:
                children.append(node.test)

        return children


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


def build_code_structure(source_code: str) -> CodeStructure:
    """
    Build complete CodeStructure from Python source code.

    Args:
        source_code: Python source code as string

    Returns:
        Complete CodeStructure with AST, functions, classes, imports, metrics

    Raises:
        SyntaxError: If source code has syntax errors
    """
    try:
        tree = ast.parse(source_code)
        source_lines = source_code.splitlines()

        # Extract functions
        function_extractor = FunctionExtractor(source_lines)
        function_extractor.visit(tree)

        # Extract classes
        class_extractor = ClassExtractor()
        class_extractor.visit(tree)

        # Extract imports
        import_extractor = ImportExtractor()
        import_extractor.visit(tree)

        # Build ASTNode tree
        node_builder = ASTNodeBuilder(source_code)
        ast_root = node_builder.build(tree)

        # Calculate basic metrics
        metrics = ComplexityMetrics(
            lines_of_code=len([line for line in source_lines if line.strip() and not line.strip().startswith("#")]),
        )

        structure = CodeStructure(
            ast=ast_root,
            functions=function_extractor.functions,
            classes=class_extractor.classes,
            imports=import_extractor.imports,
            complexity_metrics=metrics,
        )

        logger.info(
            "code_structure_built",
            function_count=len(function_extractor.functions),
            class_count=len(class_extractor.classes),
            import_count=len(import_extractor.imports),
        )

        return structure

    except SyntaxError as e:
        logger.error(
            "code_structure_build_failed",
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
