"""Code complexity metrics calculation."""

import ast
from typing import List

import radon.complexity as radon_cc
from radon.metrics import mi_visit

import structlog

from backend.models import ComplexityMetrics, FunctionInfo

logger = structlog.get_logger()


def compute_cyclomatic_complexity(source_code: str) -> int:
    """
    Compute cyclomatic complexity using radon.

    Args:
        source_code: Python source code

    Returns:
        Total cyclomatic complexity of the code
    """
    try:
        # Use radon to compute CC
        blocks = radon_cc.cc_visit(source_code)

        total_cc = sum(block.complexity for block in blocks)
        return total_cc
    except Exception as e:
        logger.warning("cyclomatic_complexity_failed", error=str(e))
        return 0


def compute_cognitive_complexity(source_code: str) -> int:
    """
    Compute cognitive complexity.

    Cognitive complexity measures how hard it is to read and understand
    the code, focusing on nesting and control flow breaks.

    Heuristic approach based on:
    - Increment for each break in linear flow (if, while, for, catch)
    - Increment for nested structures
    - Penalize deeply nested code

    Args:
        source_code: Python source code

    Returns:
        Cognitive complexity score
    """
    try:
        tree = ast.parse(source_code)

        cognitive_score = 0

        class CognitiveComplexityVisitor(ast.NodeVisitor):
            def __init__(self):
                self.nesting_level = 0
                self.score = 0

            def visit_If(self, node: ast.If) -> None:
                self.score += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1

            def visit_For(self, node: ast.For) -> None:
                self.score += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1

            def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
                self.score += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1

            def visit_While(self, node: ast.While) -> None:
                self.score += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1

            def visit_Expr(self, node: ast.Expr) -> None:
                # Check for boolean operations (and/or)
                if isinstance(node.value, ast.BoolOp):
                    # Each additional operand increases complexity
                    self.score += len(node.value.values) - 1
                self.generic_visit(node)

            def visit_ListComp(self, node: ast.ListComp) -> None:
                self.score += 1 + self.nesting_level
                self.generic_visit(node)

            def visit_SetComp(self, node: ast.SetComp) -> None:
                self.score += 1 + self.nesting_level
                self.generic_visit(node)

            def visit_DictComp(self, node: ast.DictComp) -> None:
                self.score += 1 + self.nesting_level
                self.generic_visit(node)

            def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
                self.score += 1 + self.nesting_level
                self.generic_visit(node)

            def visit_Try(self, node: ast.Try) -> None:
                self.score += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1

            def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
                self.score += 1
                self.generic_visit(node)

        visitor = CognitiveComplexityVisitor()
        visitor.visit(tree)
        return visitor.score

    except Exception as e:
        logger.warning("cognitive_complexity_failed", error=str(e))
        return 0


def compute_maintainability_index(source_code: str) -> float:
    """
    Compute maintainability index using radon.

    Args:
        source_code: Python source code

    Returns:
        Maintainability index (0-100, higher is better)
    """
    try:
        mi_score = mi_visit(source_code, multi=False)
        # mi_visit returns a float between 0 and 100
        return float(mi_score)
    except Exception as e:
        logger.warning("maintainability_index_failed", error=str(e))
        return 0.0


def compute_all_metrics(source_code: str) -> ComplexityMetrics:
    """
    Compute all complexity metrics for source code.

    Args:
        source_code: Python source code

    Returns:
        ComplexityMetrics with all computed values
    """
    lines = source_code.splitlines()
    loc = len([line for line in lines if line.strip() and not line.strip().startswith("#")])

    return ComplexityMetrics(
        cyclomatic_complexity=compute_cyclomatic_complexity(source_code),
        cognitive_complexity=compute_cognitive_complexity(source_code),
        lines_of_code=loc,
        maintainability_index=compute_maintainability_index(source_code),
    )


def enrich_function_with_complexity(source_code: str, func_info: FunctionInfo) -> FunctionInfo:
    """
    Enrich a FunctionInfo with complexity metrics using radon.

    Args:
        source_code: Full source code
        func_info: FunctionInfo to enrich

    Returns:
        FunctionInfo with complexity field populated
    """
    # Get function source
    from backend.analysis.ast_parser import get_function_source
    func_source = get_function_source(source_code, func_info.line_start, func_info.line_end)

    try:
        # Compute cyclomatic complexity using radon
        cc = radon_cc.cc_visit(func_source)
        if cc:
            func_info.complexity = cc[0].complexity
        else:
            func_info.complexity = 1
    except Exception as e:
        logger.warning(
            "function_complexity_failed",
            function=func_info.name,
            error=str(e),
        )
        func_info.complexity = 1

    return func_info


def enrich_all_functions(source_code: str, functions: List[FunctionInfo]) -> List[FunctionInfo]:
    """
    Enrich all functions with complexity metrics.

    Args:
        source_code: Full source code
        functions: List of FunctionInfo objects

    Returns:
        List of FunctionInfo with complexity populated
    """
    for func in functions:
        enrich_function_with_complexity(source_code, func)
    return functions
