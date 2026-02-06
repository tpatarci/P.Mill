"""Pattern and anti-pattern detection for Python code.

This module detects:
- Design patterns: Singleton, Factory, Strategy, Observer, Decorator, etc.
- Anti-patterns: God object, Spaghetti code, Magic numbers, etc.
- Code smells: Long methods, Large classes, Duplicated code, etc.
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

from backend.models import ClassInfo, FunctionInfo

logger = structlog.get_logger()


# Pattern detection thresholds
DEFAULT_DUPLICATE_THRESHOLD = 0.8  # Similarity threshold for duplicate detection
DEFAULT_LONG_METHOD_LINES = 30
DEFAULT_LARGE_CLASS_LINES = 200
DEFAULT_MAGIC_NUMBER_THRESHOLD = 3


@dataclass
class PatternMatch:
    """A detected design pattern."""

    pattern_type: str  # e.g., "singleton", "factory", "strategy"
    entity_name: str
    line_start: int
    line_end: int
    confidence: str  # "low", "medium", "high"
    description: str
    evidence: List[str]


@dataclass
class AntiPatternMatch:
    """A detected anti-pattern."""

    anti_pattern_type: str  # e.g., "god_object", "spaghetti_code", "magic_numbers"
    entity_name: str
    severity: str  # "low", "medium", "high", "critical"
    line_start: int
    line_end: int
    description: str
    suggestion: str


@dataclass
class CodeSmell:
    """A detected code smell."""

    smell_type: str  # e.g., "long_method", "duplicate_code", "magic_number"
    entity_name: str
    location: str  # file:line format
    severity: str
    description: str
    suggestion: Optional[str] = None


@dataclass
class DuplicateCodeBlock:
    """A block of duplicate code."""

    content: str
    locations: List[Tuple[str, int, int]]  # (entity, start, end)
    similarity: float


class SingletonPatternDetector(ast.NodeVisitor):
    """Detect Singleton pattern implementations."""

    def __init__(self, source_lines: List[str]) -> None:
        self.source_lines = source_lines
        self.matches: List[PatternMatch] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check for Singleton pattern."""
        evidence: List[str] = []
        confidence = "low"

        # Check for _instance variable
        has_instance_var = False
        has_get_instance = False

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and "_instance" in target.id:
                        has_instance_var = True
                        evidence.append("Has _instance class variable")
            elif isinstance(item, ast.FunctionDef):
                if "get_instance" in item.name or "getInstance" in item.name:
                    has_get_instance = True
                    evidence.append("Has getInstance() method")
                # Check __new__ method (Pythonic singleton)
                if item.name == "__new__":
                    evidence.append("Overrides __new__ method")
                    confidence = "high"

        # Check for common singleton patterns
        if has_instance_var or has_get_instance or "__new__" in [m.name for m in node.body if isinstance(m, ast.FunctionDef)]:
            if has_instance_var and has_get_instance:
                confidence = "high"
                evidence.append("Has instance variable and getInstance method")

            if confidence != "low":
                self.matches.append(
                    PatternMatch(
                        pattern_type="singleton",
                        entity_name=node.name,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        confidence=confidence,
                        description=f"Class {node.name} implements Singleton pattern",
                        evidence=evidence,
                    )
                )

        self.generic_visit(node)


class FactoryPatternDetector(ast.NodeVisitor):
    """Detect Factory pattern implementations."""

    def __init__(self) -> None:
        self.matches: List[PatternMatch] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check for Factory pattern."""
        # Check for Factory/Creator in name
        if any(keyword in node.name.lower() for keyword in ["factory", "creator", "builder"]):
            # Look for create/make/build methods
            factory_methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if any(keyword in item.name.lower() for keyword in ["create", "make", "build", "get"]):
                        factory_methods.append(item.name)

            if factory_methods:
                self.matches.append(
                    PatternMatch(
                        pattern_type="factory",
                        entity_name=node.name,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        confidence="medium",
                        description=f"Class {node.name} implements Factory pattern",
                        evidence=[f"Has factory methods: {', '.join(factory_methods)}"],
                    )
                )

        self.generic_visit(node)


class StrategyPatternDetector(ast.NodeVisitor):
    """Detect Strategy pattern implementations."""

    def __init__(self) -> None:
        self.matches: List[PatternMatch] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check for Strategy pattern."""
        # Check for Strategy suffix or abstract base class
        is_strategy = node.name.endswith("Strategy")

        # Look for execute/calculate/apply methods
        strategy_methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name in ["execute", "calculate", "apply", "process", "run"]:
                    strategy_methods.append(item.name)

        # Check if all methods are abstract (has pass only or raises NotImplementedError)
        all_abstract = True
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = item.body
                if body and not (isinstance(body[0], ast.Pass) or
                                 (isinstance(body[0], ast.Expr) and
                                  isinstance(body[0].value, ast.Constant) and
                                  body[0].value.value is None) or
                                 (isinstance(body[0], ast.Raise) and
                                  isinstance(body[0].exc, ast.Call) and
                                  isinstance(body[0].exc.func, ast.Name) and
                                  body[0].exc.func.id == "NotImplementedError")):
                    all_abstract = False
                    break

        if is_strategy or (strategy_methods and all_abstract):
            self.matches.append(
                PatternMatch(
                    pattern_type="strategy",
                    entity_name=node.name,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    confidence="medium",
                    description=f"Class {node.name} implements Strategy pattern",
                    evidence=[f"Strategy methods: {', '.join(strategy_methods)}"],
                )
            )

        self.generic_visit(node)


class DecoratorPatternDetector(ast.NodeVisitor):
    """Detect Decorator pattern implementations."""

    def __init__(self) -> None:
        self.matches: List[PatternMatch] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check for Decorator pattern."""
        # Function that takes a function and returns a function
        is_decorator = False
        evidence = []

        # Check decorator name
        if "decorator" in node.name.lower():
            is_decorator = True
            evidence.append("Name suggests decorator pattern")

        # Check if takes a function parameter and has nested function
        has_func_param = any(p.annotation and "Callable" in ast.unparse(p.annotation)
                             for p in node.args.args)
        has_nested_func = any(isinstance(item, ast.FunctionDef) for item in ast.walk(node))

        if has_func_param and has_nested_func:
            is_decorator = True
            evidence.append("Takes callable parameter and has nested function")

        # Check if returns a function (has closure)
        for item in node.body:
            if isinstance(item, ast.Return) and item.value:
                if isinstance(item.value, ast.Name):
                    # Check if returned value is a nested function
                    for inner in ast.walk(node):
                        if isinstance(inner, ast.FunctionDef) and inner.name == item.value.id:
                            is_decorator = True
                            evidence.append("Returns nested function (closure)")

        if is_decorator:
            self.matches.append(
                PatternMatch(
                    pattern_type="decorator",
                    entity_name=node.name,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    confidence="medium",
                    description=f"Function {node.name} implements Decorator pattern",
                    evidence=evidence,
                )
            )

        self.generic_visit(node)


class AntiPatternDetector(ast.NodeVisitor):
    """Detect anti-patterns and code smells."""

    def __init__(self, source_code: str, source_lines: List[str]) -> None:
        self.source_code = source_code
        self.source_lines = source_lines
        self.anti_patterns: List[AntiPatternMatch] = []
        self.code_smells: List[CodeSmell] = []
        self.magic_numbers: Dict[str, int] = defaultdict(int)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check for anti-patterns in classes."""
        # God object: very large class with many methods
        method_count = sum(1 for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)))
        line_count = (node.end_lineno or node.lineno) - node.lineno

        if method_count > 15 or line_count > 200:
            severity = "critical" if method_count > 30 else "high"
            self.anti_patterns.append(
                AntiPatternMatch(
                    anti_pattern_type="god_object",
                    entity_name=node.name,
                    severity=severity,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    description=f"Class {node.name} is very large ({method_count} methods, {line_count} lines)",
                    suggestion="Consider splitting into smaller classes with single responsibilities",
                )
            )

        # Check for feature envy (uses other classes' methods extensively)
        external_access: Dict[str, int] = defaultdict(int)
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func_name = self._get_call_name(child)
                if func_name and "." in func_name:
                    parts = func_name.split(".")
                    if len(parts) == 2 and parts[1] not in ["__init__", "str", "repr"]:
                        external_access[parts[0]] += 1

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check for anti-patterns in functions."""
        line_count = (node.end_lineno or node.lineno) - node.lineno

        # Long method
        if line_count > DEFAULT_LONG_METHOD_LINES:
            self.code_smells.append(
                CodeSmell(
                    smell_type="long_method",
                    entity_name=node.name,
                    location=f"{node.name}:{node.lineno}",
                    severity="medium",
                    description=f"Method {node.name} is {line_count} lines long",
                    suggestion="Consider breaking into smaller methods",
                )
            )

        # Check for magic numbers
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
                # Skip common values
                if child.value not in [0, 1, -1, 2, 100, 1000]:
                    key = f"{node.name}:{child.lineno}"
                    self.magic_numbers[key] += 1

        # Spaghetti code: deeply nested conditionals
        nesting = self._calculate_nesting(node)
        if nesting > 4:
            self.anti_patterns.append(
                AntiPatternMatch(
                    anti_pattern_type="spaghetti_code",
                    entity_name=node.name,
                    severity="high",
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    description=f"Method {node.name} has nesting depth of {nesting}",
                    suggestion="Consider refactoring with early returns or extract methods",
                )
            )

        self.generic_visit(node)

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Get the name of a function call."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return ast.unparse(node.func)
        return None

    def _calculate_nesting(self, node: ast.AST) -> int:
        """Calculate maximum nesting depth."""
        max_depth = 0

        def _visit(n: ast.AST, depth: int) -> None:
            nonlocal max_depth
            max_depth = max(max_depth, depth)

            if isinstance(n, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.Try, ast.With, ast.AsyncWith)):
                for child in ast.iter_child_nodes(n):
                    _visit(child, depth + 1)
            else:
                for child in ast.iter_child_nodes(n):
                    _visit(child, depth)

        _visit(node, 0)
        return max_depth


class DuplicateCodeDetector:
    """Detect duplicate code blocks."""

    def __init__(self, similarity_threshold: float = DEFAULT_DUPLICATE_THRESHOLD):
        self.similarity_threshold = similarity_threshold
        self.duplicates: List[DuplicateCodeBlock] = []

    def detect_duplicates(self, functions: List[FunctionInfo], source_code: str) -> List[DuplicateCodeBlock]:
        """Detect duplicate code across functions."""
        # Get function bodies
        function_bodies: List[Tuple[str, int, int, str]] = []  # (name, start, end, body)

        lines = source_code.splitlines()
        for func in functions:
            start = func.line_start - 1
            end = min(func.line_end, len(lines))
            body = "\n".join(lines[start:end])
            function_bodies.append((func.name, func.line_start, func.line_end, body))

        # Compare all pairs
        duplicates: List[DuplicateCodeBlock] = []
        for i, (name1, start1, end1, body1) in enumerate(function_bodies):
            for name2, start2, end2, body2 in function_bodies[i+1:]:
                similarity = SequenceMatcher(None, body1, body2).ratio()
                if similarity >= self.similarity_threshold:
                    # Check if this is already in our duplicates list
                    found = False
                    for dup in duplicates:
                        if abs(dup.similarity - similarity) < 0.01:
                            dup.locations.append((name2, start2, end2))
                            found = True
                            break

                    if not found:
                        duplicates.append(
                            DuplicateCodeBlock(
                                content=body1[:100] + "...",  # Truncated
                                locations=[
                                    (name1, start1, end1),
                                    (name2, start2, end2),
                                ],
                                similarity=similarity,
                            )
                        )

        self.duplicates = duplicates
        return duplicates


def detect_design_patterns(source_code: str, classes: List[ClassInfo]) -> List[PatternMatch]:
    """
    Detect design patterns in source code.

    Args:
        source_code: Python source code
        classes: List of classes to analyze

    Returns:
        List of PatternMatch objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    source_lines = source_code.splitlines()
    matches: List[PatternMatch] = []

    # Run all pattern detectors
    detectors = [
        SingletonPatternDetector(source_lines),
        FactoryPatternDetector(),
        StrategyPatternDetector(),
        DecoratorPatternDetector(),
    ]

    for detector in detectors:
        detector.visit(tree)
        matches.extend(detector.matches)

    return matches


def detect_anti_patterns(
    source_code: str,
    classes: List[ClassInfo],
    functions: List[FunctionInfo],
) -> Tuple[List[AntiPatternMatch], List[CodeSmell]]:
    """
    Detect anti-patterns and code smells.

    Args:
        source_code: Python source code
        classes: List of classes to analyze
        functions: List of functions to analyze

    Returns:
        Tuple of (anti_patterns, code_smells)
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return [], []

    source_lines = source_code.splitlines()
    detector = AntiPatternDetector(source_code, source_lines)
    detector.visit(tree)

    # Detect duplicate code
    duplicate_detector = DuplicateCodeDetector()
    duplicates = duplicate_detector.detect_duplicates(functions, source_code)

    for dup in duplicates:
        detector.code_smells.append(
            CodeSmell(
                smell_type="duplicate_code",
                entity_name=", ".join(loc[0] for loc in dup.locations),
                location=", ".join(f"{loc[0]}:{loc[1]}" for loc in dup.locations),
                severity="medium",
                description=f"Duplicate code found ({int(dup.similarity * 100)}% similarity)",
                suggestion="Extract duplicate code into a shared function",
            )
        )

    return detector.anti_patterns, detector.code_smells


def generate_pattern_report(
    patterns: List[PatternMatch],
    anti_patterns: List[AntiPatternMatch],
    code_smells: List[CodeSmell],
) -> dict:
    """
    Generate a comprehensive pattern analysis report.

    Args:
        patterns: Detected design patterns
        anti_patterns: Detected anti-patterns
        code_smells: Detected code smells

    Returns:
        Dict with summary and details
    """
    # Count by type
    pattern_counts = Counter(p.pattern_type for p in patterns)
    anti_pattern_counts = Counter(a.anti_pattern_type for a in anti_patterns)
    smell_counts = Counter(s.smell_type for s in code_smells)

    # Count by severity
    severity_counts = defaultdict(int)
    for a in anti_patterns:
        severity_counts[a.severity] += 1
    for s in code_smells:
        severity_counts[s.severity] += 1

    return {
        "summary": {
            "design_patterns_found": len(patterns),
            "anti_patterns_found": len(anti_patterns),
            "code_smells_found": len(code_smells),
            "by_pattern_type": dict(pattern_counts),
            "by_anti_pattern_type": dict(anti_pattern_counts),
            "by_smell_type": dict(smell_counts),
            "by_severity": dict(severity_counts),
        },
        "design_patterns": [
            {
                "type": p.pattern_type,
                "entity": p.entity_name,
                "line": p.line_start,
                "confidence": p.confidence,
                "description": p.description,
                "evidence": p.evidence,
            }
            for p in patterns
        ],
        "anti_patterns": [
            {
                "type": a.anti_pattern_type,
                "entity": a.entity_name,
                "severity": a.severity,
                "line": a.line_start,
                "description": a.description,
                "suggestion": a.suggestion,
            }
            for a in anti_patterns
        ],
        "code_smells": [
            {
                "type": s.smell_type,
                "entity": s.entity_name,
                "location": s.location,
                "severity": s.severity,
                "description": s.description,
                "suggestion": s.suggestion,
            }
            for s in code_smells
        ],
    }
