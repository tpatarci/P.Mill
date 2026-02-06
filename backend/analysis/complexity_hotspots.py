"""Complexity hotspot detection for Python code.

This module analyzes code for complexity-related issues:
- High cyclomatic complexity functions
- Deeply nested code structures
- Long parameter lists
- Large classes/functions
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional

import structlog
from radon.complexity import cc_visit

from backend.analysis.complexity import (
    compute_cognitive_complexity,
    compute_cyclomatic_complexity,
)
from backend.models import ClassInfo, ComplexityMetrics, FunctionInfo

logger = structlog.get_logger()


# Thresholds for complexity hotspots
DEFAULT_CYCLOMATIC_THRESHOLD = 10
DEFAULT_COGNITIVE_THRESHOLD = 15
DEFAULT_NESTING_THRESHOLD = 4
DEFAULT_PARAMETER_COUNT_THRESHOLD = 5
DEFAULT_FUNCTION_LOC_THRESHOLD = 50
DEFAULT_CLASS_LOC_THRESHOLD = 300
DEFAULT_METHOD_COUNT_THRESHOLD = 10


@dataclass
class ComplexityHotspot:
    """A complexity hotspot found in code."""

    entity_type: str  # "function" or "class"
    name: str
    qualified_name: str
    file_path: str
    line_start: int
    line_end: int
    hotspot_type: str  # "high_cc", "high_cognitive", "deep_nesting", "long_params", "large_size"
    severity: str  # "low", "medium", "high", "critical"
    value: float  # The measured value (e.g., CC=15)
    threshold: float  # The threshold that was exceeded
    description: str
    suggestion: Optional[str] = None


@dataclass
class NestingDepth:
    """Nesting depth analysis result."""

    max_depth: int
    line_of_max_depth: int
    context: str  # Description of what caused max depth


class NestingAnalyzer(ast.NodeVisitor):
    """AST visitor to find maximum nesting depth."""

    # Node types that increase nesting
    NESTING_NODES = (
        ast.If,
        ast.While,
        ast.For,
        ast.AsyncFor,
        ast.Try,
        ast.With,
        ast.AsyncWith,
        ast.Lambda,
        ast.ListComp,
        ast.DictComp,
        ast.SetComp,
        ast.GeneratorExp,
    )

    def __init__(self) -> None:
        self.max_depth = 0
        self.current_depth = 0
        self.max_depth_line = 1
        self.max_depth_context = ""

    def visit(self, node: ast.AST) -> None:
        """Visit a node and track nesting depth."""
        is_nesting = isinstance(node, self.NESTING_NODES)

        if is_nesting:
            self.current_depth += 1
            if self.current_depth > self.max_depth:
                self.max_depth = self.current_depth
                self.max_depth_line = getattr(node, "lineno", 1)
                self.max_depth_context = f"{node.__class__.__name__} at line {self.max_depth_line}"

        self.generic_visit(node)

        if is_nesting:
            self.current_depth -= 1

    def get_result(self) -> NestingDepth:
        """Get the nesting depth analysis result."""
        return NestingDepth(
            max_depth=self.max_depth,
            line_of_max_depth=self.max_depth_line,
            context=self.max_depth_context,
        )


def analyze_nesting_depth(source_code: str) -> NestingDepth:
    """
    Analyze the maximum nesting depth of source code.

    Args:
        source_code: Python source code

    Returns:
        NestingDepth with max depth and location
    """
    try:
        tree = ast.parse(source_code)
        analyzer = NestingAnalyzer()
        analyzer.visit(tree)
        return analyzer.get_result()
    except SyntaxError:
        return NestingDepth(max_depth=0, line_of_max_depth=0, context="syntax error")


def analyze_function_hotspots(
    function: FunctionInfo,
    source_code: str,
    file_path: str = "",
    thresholds: dict | None = None,
) -> List[ComplexityHotspot]:
    """
    Analyze a function for complexity hotspots.

    Args:
        function: FunctionInfo to analyze
        source_code: Full source code containing the function
        file_path: Path to the file (for reporting)
        thresholds: Optional dict of threshold values

    Returns:
        List of ComplexityHotspots found
    """
    if thresholds is None:
        thresholds = {}

    cc_threshold = thresholds.get("cyclomatic", DEFAULT_CYCLOMATIC_THRESHOLD)
    cognitive_threshold = thresholds.get("cognitive", DEFAULT_COGNITIVE_THRESHOLD)
    nesting_threshold = thresholds.get("nesting", DEFAULT_NESTING_THRESHOLD)
    param_threshold = thresholds.get("parameters", DEFAULT_PARAMETER_COUNT_THRESHOLD)
    loc_threshold = thresholds.get("function_loc", DEFAULT_FUNCTION_LOC_THRESHOLD)

    hotspots: List[ComplexityHotspot] = []

    # Get function source
    from backend.analysis.ast_parser import get_function_source

    try:
        func_source = get_function_source(source_code, function.line_start, function.line_end)
    except Exception:
        func_source = ""

    # Check cyclomatic complexity
    cc = compute_cyclomatic_complexity(func_source)
    if cc > cc_threshold:
        severity = _get_cc_severity(cc)
        hotspots.append(
            ComplexityHotspot(
                entity_type="function",
                name=function.name,
                qualified_name=function.name,
                file_path=file_path,
                line_start=function.line_start,
                line_end=function.line_end,
                hotspot_type="high_cc",
                severity=severity,
                value=cc,
                threshold=cc_threshold,
                description=f"Function has cyclomatic complexity of {cc} (threshold: {cc_threshold})",
                suggestion=_get_cc_suggestion(cc),
            )
        )

    # Check cognitive complexity
    cognitive = compute_cognitive_complexity(func_source)
    if cognitive > cognitive_threshold:
        severity = _get_cognitive_severity(cognitive)
        hotspots.append(
            ComplexityHotspot(
                entity_type="function",
                name=function.name,
                qualified_name=function.name,
                file_path=file_path,
                line_start=function.line_start,
                line_end=function.line_end,
                hotspot_type="high_cognitive",
                severity=severity,
                value=cognitive,
                threshold=cognitive_threshold,
                description=f"Function has cognitive complexity of {cognitive} (threshold: {cognitive_threshold})",
                suggestion=_get_cognitive_suggestion(cognitive),
            )
        )

    # Check nesting depth
    nesting = analyze_nesting_depth(func_source)
    if nesting.max_depth > nesting_threshold:
        severity = _get_nesting_severity(nesting.max_depth)
        hotspots.append(
            ComplexityHotspot(
                entity_type="function",
                name=function.name,
                qualified_name=function.name,
                file_path=file_path,
                line_start=function.line_start,
                line_end=function.line_end,
                hotspot_type="deep_nesting",
                severity=severity,
                value=nesting.max_depth,
                threshold=nesting_threshold,
                description=f"Function has nesting depth of {nesting.max_depth} at line {nesting.line_of_max_depth} ({nesting.context})",
                suggestion=_get_nesting_suggestion(nesting.max_depth),
            )
        )

    # Check parameter count
    param_count = len(function.parameters)
    if param_count > param_threshold:
        severity = _get_param_severity(param_count)
        hotspots.append(
            ComplexityHotspot(
                entity_type="function",
                name=function.name,
                qualified_name=function.name,
                file_path=file_path,
                line_start=function.line_start,
                line_end=function.line_end,
                hotspot_type="long_params",
                severity=severity,
                value=param_count,
                threshold=param_threshold,
                description=f"Function has {param_count} parameters (threshold: {param_threshold})",
                suggestion=_get_param_suggestion(param_count),
            )
        )

    # Check function size (LOC)
    loc = function.line_end - function.line_start + 1
    if loc > loc_threshold:
        severity = _get_loc_severity(loc)
        hotspots.append(
            ComplexityHotspot(
                entity_type="function",
                name=function.name,
                qualified_name=function.name,
                file_path=file_path,
                line_start=function.line_start,
                line_end=function.line_end,
                hotspot_type="large_size",
                severity=severity,
                value=loc,
                threshold=loc_threshold,
                description=f"Function is {loc} lines long (threshold: {loc_threshold})",
                suggestion=_get_loc_suggestion(loc),
            )
        )

    return hotspots


def analyze_class_hotspots(
    cls: ClassInfo,
    source_code: str,
    file_path: str = "",
    thresholds: dict | None = None,
) -> List[ComplexityHotspot]:
    """
    Analyze a class for complexity hotspots.

    Args:
        cls: ClassInfo to analyze
        source_code: Full source code containing the class
        file_path: Path to the file (for reporting)
        thresholds: Optional dict of threshold values

    Returns:
        List of ComplexityHotspots found
    """
    if thresholds is None:
        thresholds = {}

    method_threshold = thresholds.get("methods", DEFAULT_METHOD_COUNT_THRESHOLD)
    loc_threshold = thresholds.get("class_loc", DEFAULT_CLASS_LOC_THRESHOLD)

    hotspots: List[ComplexityHotspot] = []

    # Check method count
    method_count = len(cls.methods)
    if method_count > method_threshold:
        severity = _get_method_count_severity(method_count)
        hotspots.append(
            ComplexityHotspot(
                entity_type="class",
                name=cls.name,
                qualified_name=cls.name,
                file_path=file_path,
                line_start=cls.line_start,
                line_end=cls.line_end,
                hotspot_type="many_methods",
                severity=severity,
                value=method_count,
                threshold=method_threshold,
                description=f"Class has {method_count} methods (threshold: {method_threshold})",
                suggestion=_get_method_suggestion(method_count),
            )
        )

    # Check class size (LOC)
    loc = cls.line_end - cls.line_start + 1
    if loc > loc_threshold:
        severity = _get_class_loc_severity(loc)
        hotspots.append(
            ComplexityHotspot(
                entity_type="class",
                name=cls.name,
                qualified_name=cls.name,
                file_path=file_path,
                line_start=cls.line_start,
                line_end=cls.line_end,
                hotspot_type="large_size",
                severity=severity,
                value=loc,
                threshold=loc_threshold,
                description=f"Class is {loc} lines long (threshold: {loc_threshold})",
                suggestion=_get_class_suggestion(loc),
            )
        )

    return hotspots


def analyze_module_hotspots(
    source_code: str,
    file_path: str = "",
    functions: List[FunctionInfo] | None = None,
    classes: List[ClassInfo] | None = None,
    thresholds: dict | None = None,
) -> List[ComplexityHotspot]:
    """
    Analyze a module for all complexity hotspots.

    Args:
        source_code: Python source code to analyze
        file_path: Path to the file (for reporting)
        functions: List of functions to analyze (if None, extracts from source)
        classes: List of classes to analyze (if None, extracts from source)
        thresholds: Optional dict of threshold values

    Returns:
        List of all ComplexityHotspots found
    """
    from backend.analysis.ast_parser import parse_python_file

    # Extract functions and classes if not provided
    if functions is None or classes is None:
        tree, all_functions, all_classes = parse_python_file(source_code)
        if functions is None:
            functions = all_functions
        if classes is None:
            classes = all_classes

    hotspots: List[ComplexityHotspot] = []

    # Analyze all functions
    for func in functions or []:
        func_hotspots = analyze_function_hotspots(func, source_code, file_path, thresholds)
        hotspots.extend(func_hotspots)

    # Analyze all classes
    for cls in classes or []:
        cls_hotspots = analyze_class_hotspots(cls, source_code, file_path, thresholds)
        hotspots.extend(cls_hotspots)

    # Sort by severity and value
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    hotspots.sort(key=lambda h: (severity_order.get(h.severity, 4), -h.value))

    return hotspots


def generate_complexity_report(hotspots: List[ComplexityHotspot]) -> dict:
    """
    Generate a summary report from complexity hotspots.

    Args:
        hotspots: List of ComplexityHotspots

    Returns:
        Dict with summary statistics and grouped hotspots
    """
    # Count by type
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_entity: dict[str, int] = {}

    for hotspot in hotspots:
        by_type[hotspot.hotspot_type] = by_type.get(hotspot.hotspot_type, 0) + 1
        by_severity[hotspot.severity] = by_severity.get(hotspot.severity, 0) + 1
        by_entity[hotspot.entity_type] = by_entity.get(hotspot.entity_type, 0) + 1

    # Group hotspots by entity
    by_entity_name: dict[str, List[ComplexityHotspot]] = {}
    for hotspot in hotspots:
        key = f"{hotspot.entity_type}:{hotspot.qualified_name}"
        if key not in by_entity_name:
            by_entity_name[key] = []
        by_entity_name[key].append(hotspot)

    return {
        "total_hotspots": len(hotspots),
        "by_type": by_type,
        "by_severity": by_severity,
        "by_entity_type": by_entity,
        "by_entity_name": {k: len(v) for k, v in by_entity_name.items()},
        "hotspots": [
            {
                "entity": h.qualified_name,
                "type": h.hotspot_type,
                "severity": h.severity,
                "value": h.value,
                "threshold": h.threshold,
                "description": h.description,
            }
            for h in hotspots
        ],
    }


# Severity determination helpers


def _get_cc_severity(cc: int) -> str:
    """Get severity level for cyclomatic complexity."""
    if cc >= 50:
        return "critical"
    if cc >= 20:
        return "high"
    if cc >= 10:
        return "medium"
    return "low"


def _get_cognitive_severity(cognitive: int) -> str:
    """Get severity level for cognitive complexity."""
    if cognitive >= 30:
        return "critical"
    if cognitive >= 20:
        return "high"
    if cognitive >= 15:
        return "medium"
    return "low"


def _get_nesting_severity(depth: int) -> str:
    """Get severity level for nesting depth."""
    if depth >= 6:
        return "critical"
    if depth >= 5:
        return "high"
    if depth >= 4:
        return "medium"
    return "low"


def _get_param_severity(count: int) -> str:
    """Get severity level for parameter count."""
    if count >= 10:
        return "critical"
    if count >= 7:
        return "high"
    if count >= 5:
        return "medium"
    return "low"


def _get_loc_severity(loc: int) -> str:
    """Get severity level for function size."""
    if loc >= 100:
        return "critical"
    if loc >= 75:
        return "high"
    if loc >= 50:
        return "medium"
    return "low"


def _get_method_count_severity(count: int) -> str:
    """Get severity level for method count."""
    if count >= 20:
        return "critical"
    if count >= 15:
        return "high"
    if count >= 10:
        return "medium"
    return "low"


def _get_class_loc_severity(loc: int) -> str:
    """Get severity level for class size."""
    if loc >= 500:
        return "critical"
    if loc >= 400:
        return "high"
    if loc >= 300:
        return "medium"
    return "low"


# Suggestion helpers


def _get_cc_suggestion(cc: int) -> str:
    """Get suggestion for high cyclomatic complexity."""
    if cc >= 50:
        return "Refactor this function into smaller functions with single responsibilities."
    return "Consider breaking this function into smaller, more focused functions."


def _get_cognitive_suggestion(cognitive: int) -> str:
    """Get suggestion for high cognitive complexity."""
    return "Reduce nesting by using early returns, guard clauses, or extracting nested logic into separate functions."


def _get_nesting_suggestion(depth: int) -> str:
    """Get suggestion for deep nesting."""
    return "Consider flattening the code structure with early returns, guard clauses, or extract nested blocks into separate functions."


def _get_param_suggestion(count: int) -> str:
    """Get suggestion for long parameter lists."""
    return "Consider grouping related parameters into a dataclass or using **kwargs for optional parameters."


def _get_loc_suggestion(loc: int) -> str:
    """Get suggestion for large functions."""
    return "This function is too long. Consider breaking it into smaller, single-purpose functions."


def _get_method_suggestion(count: int) -> str:
    """Get suggestion for classes with many methods."""
    return "This class may have too many responsibilities. Consider splitting it into smaller, more focused classes."


def _get_class_suggestion(loc: int) -> str:
    """Get suggestion for large classes."""
    return "This class is very large. Consider extracting related functionality into separate classes or modules."
