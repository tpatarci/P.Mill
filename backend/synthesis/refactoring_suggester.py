"""Refactoring suggestions for code improvement.

This module provides:
- Extract method suggestions
- Introduce parameter object suggestions
- Replace conditional with polymorphism suggestions
- Simplify conditional expressions
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional

import structlog

from backend.models import FunctionInfo

logger = structlog.get_logger()


@dataclass
class RefactoringSuggestion:
    """A suggested refactoring."""

    suggestion_id: str
    suggestion_type: str  # "extract_method", "parameter_object", etc.
    function_name: str
    line_start: int
    line_end: int
    description: str
    suggested_code: str
    confidence: str = "medium"
    effort: str = "medium"  # "low", "medium", "high"


class RefactoringSuggester(ast.NodeVisitor):
    """Suggest refactorings for code improvement."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.suggestions: List[RefactoringSuggestion] = []
        self.current_class: Optional[str] = None
        self.current_function: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        old_function = self.current_function
        self.current_function = f"{self.current_class}.{node.name}" if self.current_class else node.name

        # Analyze for refactoring opportunities
        self._suggest_extract_method(node)
        self._suggest_parameter_object(node)
        self._suggest_simplify_conditionals(node)
        self._suggest_replace_magic_numbers(node)

        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self.visit_FunctionDef(node)

    def _suggest_extract_method(self, node: ast.FunctionDef) -> None:
        """Suggest extracting a method if function is too long."""
        # Count lines
        line_count = (node.end_lineno or node.lineno) - node.lineno

        if line_count > 30:
            # Suggest extraction
            suggestion = RefactoringSuggestion(
                suggestion_id=f"{self.current_function}:extract_method",
                suggestion_type="extract_method",
                function_name=self.current_function or node.name,
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                description=f"Function is {line_count} lines long. Consider extracting logical blocks into smaller methods.",
                suggested_code=f"""# Extract logical blocks into helper functions
def extracted_function_name():
    # Extracted logic here
    pass

def {node.name}():
    result = extracted_function_name()
    return result
""",
                confidence="medium",
                effort="medium",
            )
            self.suggestions.append(suggestion)

    def _suggest_parameter_object(self, node: ast.FunctionDef) -> None:
        """Suggest introducing a parameter object if too many parameters."""
        param_count = len([arg for arg in node.args.args if arg.arg not in ["self", "cls"]])

        if param_count > 5:
            params = [arg.arg for arg in node.args.args if arg.arg not in ["self", "cls"]]
            suggestion = RefactoringSuggestion(
                suggestion_id=f"{self.current_function}:parameter_object",
                suggestion_type="parameter_object",
                function_name=self.current_function or node.name,
                line_start=node.lineno,
                line_end=node.lineno,
                description=f"Function has {param_count} parameters. Consider grouping related parameters into a dataclass.",
                suggested_code=f"""from dataclasses import dataclass

@dataclass
class {node.name.title()}Config:
    {chr(10).join(f'    {p}: type' for p in params)}

def {node.name}(config: {node.name.title()}Config):
    # Use config.p, config.q, etc.
    pass
""",
                confidence="low",
                effort="high",
            )
            self.suggestions.append(suggestion)

    def _suggest_simplify_conditionals(self, node: ast.FunctionDef) -> None:
        """Suggest simplifying complex conditionals."""
        for child in ast.walk(node):
            if isinstance(child, ast.If):
                # Check for nested if-else that could be simplified
                if len(child.orelse) == 1 and isinstance(child.orelse[0], ast.If):
                    # Chained if-elif-else - suggest improvement
                    suggestion = RefactoringSuggestion(
                        suggestion_id=f"{self.current_function}:simplify_conditional:{child.lineno}",
                        suggestion_type="simplify_conditional",
                        function_name=self.current_function or node.name,
                        line_start=child.lineno,
                        line_end=child.lineno,
                        description="Consider using guard clauses or early returns to reduce nesting.",
                        suggested_code="# Use early returns to reduce nesting:\n# if not condition:\n#     return None\n# # Main logic here",
                        confidence="low",
                        effort="low",
                    )
                    self.suggestions.append(suggestion)

    def _suggest_replace_magic_numbers(self, node: ast.FunctionDef) -> None:
        """Suggest replacing magic numbers with named constants."""
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
                # Skip common values
                if child.value in [0, 1, -1, 2, 100, 1000]:
                    continue

                suggestion = RefactoringSuggestion(
                    suggestion_id=f"{self.current_function}:magic_number:{child.lineno}",
                    suggestion_type="replace_magic_number",
                    function_name=self.current_function or node.name,
                    line_start=child.lineno,
                    line_end=child.lineno,
                    description=f"Replace magic number {child.value} with a named constant.",
                    suggested_code=f"# Define constant at module level:\n# {node.name.upper()}_CONSTANT = {child.value}\n# Then use the constant in your code",
                    confidence="low",
                    effort="low",
                )
                self.suggestions.append(suggestion)


def suggest_refactorings(
    source_code: str,
    functions: List[FunctionInfo],
) -> List[RefactoringSuggestion]:
    """
    Suggest refactorings for code.

    Args:
        source_code: Python source code
        functions: List of functions to analyze

    Returns:
        List of RefactoringSuggestion objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    suggester = RefactoringSuggester(source_code)
    suggester.visit(tree)

    return suggester.suggestions


def generate_refactoring_report(suggestions: List[RefactoringSuggestion]) -> dict:
    """
    Generate refactoring report.

    Args:
        suggestions: List of refactoring suggestions

    Returns:
        Dict with summary and details
    """
    return {
        "summary": {
            "total_suggestions": len(suggestions),
            "by_type": {
                s.suggestion_type: len([sug for sug in suggestions if sug.suggestion_type == s.suggestion_type])
                for s in suggestions
            },
            "by_effort": {
                "low": len([s for s in suggestions if s.effort == "low"]),
                "medium": len([s for s in suggestions if s.effort == "medium"]),
                "high": len([s for s in suggestions if s.effort == "high"]),
            },
        },
        "suggestions": [
            {
                "id": s.suggestion_id,
                "type": s.suggestion_type,
                "function": s.function_name,
                "line": s.line_start,
                "description": s.description,
                "suggested_code": s.suggested_code[:200],  # Truncate for report
                "confidence": s.confidence,
                "effort": s.effort,
            }
            for s in suggestions
        ],
    }
