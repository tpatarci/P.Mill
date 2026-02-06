"""Extract deterministic facts from function ASTs."""

import ast
from typing import List

import structlog
from radon.complexity import cc_visit

from backend.analysis.ast_parser import BUILTINS
from backend.models import FunctionFacts, ParameterInfo

logger = structlog.get_logger()


class FactExtractorVisitor(ast.NodeVisitor):
    """Visit function AST nodes to extract facts."""

    def __init__(self):
        """Initialize visitor."""
        self.facts = {
            "has_bare_except": False,
            "has_broad_except": False,
            "has_mutable_default_args": False,
            "uses_open_without_with": False,
            "has_none_checks": [],
            "has_type_checks": [],
            "raise_types": [],
            "caught_types": [],
            "calls": [],
            "has_return_on_all_paths": False,
            "has_unreachable_code": False,
            "shadows_builtin": [],
            "star_imports_used": False,
            "uses_command_execution": False,
            "command_execution_has_fstring": False,
        }
        self.none_checked_vars: set[str] = set()
        self.type_checked_vars: set[str] = set()
        self.after_unconditional_return = False

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Visit exception handler."""
        if node.type is None:
            # Bare except:
            self.facts["has_bare_except"] = True
        else:
            # Check if catching Exception or BaseException
            exception_name = ast.unparse(node.type)
            if exception_name in ("Exception", "BaseException"):
                self.facts["has_broad_except"] = True
            self.facts["caught_types"].append(exception_name)
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        """Visit raise statement."""
        if node.exc:
            exception_type = ast.unparse(node.exc)
            # Extract just the exception class name
            if "(" in exception_type:
                exception_type = exception_type[:exception_type.index("(")]
            self.facts["raise_types"].append(exception_type)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call."""
        call_name = ast.unparse(node.func)
        self.facts["calls"].append(call_name)

        # Check for open() without with
        if call_name == "open":
            # Check if we're inside a With context
            # This is a simplification - proper check needs parent tracking
            self.facts["uses_open_without_with"] = True

        # Check for command execution
        if call_name in ("os.system", "subprocess.call", "subprocess.run",
                         "subprocess.Popen", "os.popen"):
            self.facts["uses_command_execution"] = True
            # Check if arguments contain f-strings
            for arg in node.args:
                if isinstance(arg, ast.JoinedStr):  # f-string
                    self.facts["command_execution_has_fstring"] = True

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        """Visit comparison to detect None checks."""
        # Check for "x is None" or "x is not None"
        for i, op in enumerate(node.ops):
            if isinstance(op, (ast.Is, ast.IsNot)):
                comparator = node.comparators[i]
                if isinstance(comparator, ast.Constant) and comparator.value is None:
                    # Left side is being checked against None
                    if isinstance(node.left, ast.Name):
                        self.none_checked_vars.add(node.left.id)
                        self.facts["has_none_checks"].append(node.left.id)

        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Visit if statement to detect type checks."""
        # Check for isinstance() calls in test
        if isinstance(node.test, ast.Call):
            call_name = ast.unparse(node.test.func)
            if call_name == "isinstance" and node.test.args:
                arg = node.test.args[0]
                if isinstance(arg, ast.Name):
                    self.type_checked_vars.add(arg.id)
                    self.facts["has_type_checks"].append(arg.id)

        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        """Visit return statement."""
        # Mark that we saw a return (for unreachable code detection)
        self.after_unconditional_return = True
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        """Visit with statement."""
        # Note: Proper detection of open() with/without 'with' requires two-pass analysis
        # For now, we mark any with statement containing open() as safe
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                call_name = ast.unparse(item.context_expr.func)
                if call_name == "open":
                    # This open() is safe - it's in a with statement
                    # Clear the flag that was set in visit_Call
                    self.facts["uses_open_without_with"] = False

        self.generic_visit(node)


def extract_function_facts(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_code: str,
    class_name: str | None = None
) -> FunctionFacts:
    """
    Extract all deterministic facts from a function AST node.

    Args:
        func_node: Function AST node
        source_code: Full source code (for extracting function source)
        class_name: Name of containing class if this is a method

    Returns:
        FunctionFacts model with all extracted facts
    """
    # Extract basic info
    function_name = func_node.name
    qualified_name = f"{class_name}.{function_name}" if class_name else function_name
    line_start = func_node.lineno
    line_end = func_node.end_lineno or line_start
    is_method = class_name is not None
    is_async = isinstance(func_node, ast.AsyncFunctionDef)

    # Extract decorators
    decorators = [ast.unparse(dec) for dec in func_node.decorator_list]

    # Extract parameters
    parameters: List[ParameterInfo] = []
    shadows_builtin: List[str] = []
    has_mutable_default_args = False

    for arg in func_node.args.args:
        param_name = arg.arg
        type_hint = ast.unparse(arg.annotation) if arg.annotation else None
        has_default = False
        default_is_mutable = False

        # Check if shadows builtin
        if param_name in BUILTINS:
            shadows_builtin.append(param_name)

        parameters.append(ParameterInfo(
            name=param_name,
            type_hint=type_hint,
            has_default=has_default,
            default_is_mutable=default_is_mutable
        ))

    # Check for defaults
    defaults = func_node.args.defaults
    if defaults:
        # Defaults apply to the last N parameters
        num_defaults = len(defaults)
        for i, default in enumerate(defaults):
            param_idx = len(parameters) - num_defaults + i
            if param_idx >= 0:
                parameters[param_idx].has_default = True
                # Check if default is mutable (list, dict, set)
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    parameters[param_idx].default_is_mutable = True
                    has_mutable_default_args = True

    # Extract return annotation
    return_annotation = None
    if func_node.returns:
        return_annotation = ast.unparse(func_node.returns)

    # Extract docstring
    docstring = ast.get_docstring(func_node)
    has_docstring = docstring is not None

    # Extract function source code
    source_lines = source_code.splitlines()
    func_source = "\n".join(source_lines[line_start - 1:line_end])

    # Calculate LOC (non-empty, non-comment lines in function body)
    loc = line_end - line_start + 1

    # Calculate cyclomatic complexity using radon
    try:
        complexity_results = cc_visit(func_source)
        cyclomatic_complexity = complexity_results[0].complexity if complexity_results else 1
    except Exception as e:
        logger.warning("complexity_calculation_failed", error=str(e), function=function_name)
        cyclomatic_complexity = 1

    # Visit AST to extract behavioral facts
    visitor = FactExtractorVisitor()
    visitor.visit(func_node)

    # Deduplicate lists
    has_none_checks = list(set(visitor.facts["has_none_checks"]))
    has_type_checks = list(set(visitor.facts["has_type_checks"]))
    raise_types = list(set(visitor.facts["raise_types"]))
    caught_types = list(set(visitor.facts["caught_types"]))
    calls = list(dict.fromkeys(visitor.facts["calls"]))  # preserve order, deduplicate

    # Check for return on all paths (simplified heuristic)
    has_return = any(isinstance(node, ast.Return) for node in ast.walk(func_node))
    has_return_on_all_paths = has_return

    # Check for unreachable code (simplified)
    has_unreachable_code = _check_unreachable_code(func_node)

    return FunctionFacts(
        function_name=function_name,
        qualified_name=qualified_name,
        line_start=line_start,
        line_end=line_end,
        is_method=is_method,
        is_async=is_async,
        class_name=class_name,
        decorators=decorators,
        parameters=parameters,
        return_annotation=return_annotation,
        has_docstring=has_docstring,
        docstring=docstring,
        cyclomatic_complexity=cyclomatic_complexity,
        loc=loc,
        source_code=func_source,
        has_bare_except=visitor.facts["has_bare_except"],
        has_broad_except=visitor.facts["has_broad_except"],
        has_mutable_default_args=has_mutable_default_args,
        uses_open_without_with=visitor.facts["uses_open_without_with"],
        has_none_checks=has_none_checks,
        has_type_checks=has_type_checks,
        raise_types=raise_types,
        caught_types=caught_types,
        calls=calls,
        has_return_on_all_paths=has_return_on_all_paths,
        has_unreachable_code=has_unreachable_code,
        shadows_builtin=shadows_builtin,
        star_imports_used=visitor.facts["star_imports_used"],
        uses_command_execution=visitor.facts["uses_command_execution"],
        command_execution_has_fstring=visitor.facts["command_execution_has_fstring"],
    )


def _check_unreachable_code(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """
    Check for unreachable code after unconditional return/raise.

    This is a simplified check that looks for statements after a return/raise
    at the same indentation level.
    """
    for node in ast.walk(func_node):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            # Check body for unconditional return followed by more statements
            if hasattr(node, 'body') and len(node.body) > 1:
                for i, stmt in enumerate(node.body[:-1]):
                    if isinstance(stmt, (ast.Return, ast.Raise)):
                        # Check if there are more statements after this
                        if i + 1 < len(node.body):
                            return True

    return False
