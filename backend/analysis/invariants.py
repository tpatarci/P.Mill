"""Invariant detection for Python code.

This module detects:
- Loop invariants
- Class invariants
- Data structure invariants
- Invariant preservation verification
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

from backend.models import ClassInfo, FunctionInfo

logger = structlog.get_logger()


@dataclass
class LoopInvariant:
    """An invariant detected for a loop."""

    loop_type: str  # "for", "while"
    loop_variable: Optional[str]
    invariants: List[str]
    line_start: int
    line_end: int


@dataclass
class ClassInvariant:
    """An invariant detected for a class."""

    class_name: str
    invariants: List[str]
    state_constraints: List[str]
    confidence: str


@dataclass
class InvariantViolation:
    """A detected invariant violation."""

    invariant_type: str  # "loop", "class", "data_structure"
    entity_name: str
    location: str
    severity: str
    description: str
    suggestion: Optional[str] = None


class LoopInvariantDetector(ast.NodeVisitor):
    """Detect loop invariants."""

    def __init__(self) -> None:
        self.loop_invariants: List[LoopInvariant] = []

    def visit_For(self, node: ast.For) -> None:
        """Analyze for loop for invariants."""
        loop_var = None
        if isinstance(node.target, ast.Name):
            loop_var = node.target.id

        invariants = []

        # Detect common patterns
        # 1. Accumulator pattern: sum = 0; for x in items: sum += x
        #    Invariant: sum is the sum of processed elements
        # 2. Counter pattern: count = 0; for x in items: if condition: count += 1
        #    Invariant: count is the count of matching elements

        # Look for variable initialization before loop
        invariants.extend(self._detect_accumulator_invariants(node))

        if invariants or loop_var:
            self.loop_invariants.append(
                LoopInvariant(
                    loop_type="for",
                    loop_variable=loop_var,
                    invariants=invariants,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                )
            )

        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        """Analyze while loop for invariants."""
        invariants = []

        # Detect common while loop patterns
        # 1. Counter pattern: i = 0; while i < n: i += 1
        #    Invariant: i is always <= n

        # Look for comparison in condition
        if isinstance(node.test, ast.Compare):
            condition = ast.unparse(node.test)
            if "<" in condition or "<=" in condition:
                # Likely a bounded loop
                invariants.append(f"Loop bounded by condition: {condition}")

        self.loop_invariants.append(
            LoopInvariant(
                loop_type="while",
                loop_variable=None,
                invariants=invariants,
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
            )
        )

        self.generic_visit(node)

    def _detect_accumulator_invariants(self, node: ast.For) -> List[str]:
        """Detect accumulator patterns in for loop."""
        invariants = []

        # Look for augmented assignments (+=, *=, etc.) in loop body
        for child in ast.walk(node):
            if isinstance(child, ast.AugAssign):
                if isinstance(child.target, ast.Name):
                    var_name = child.target.id
                    op = child.op
                    if isinstance(op, ast.Add):
                        invariants.append(f"{var_name} accumulates values across iterations")
                    elif isinstance(op, ast.Mult):
                        invariants.append(f"{var_name} multiplies values across iterations")

        return invariants


class ClassInvariantDetector(ast.NodeVisitor):
    """Detect class invariants."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.class_invariants: Dict[str, ClassInvariant] = {}
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Analyze class for invariants."""
        self.current_class = node.name
        invariants: List[str] = []
        state_constraints: List[str] = []

        # Check __init__ for validation logic
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                init_invariants = self._analyze_init_for_invariants(item)
                invariants.extend(init_invariants)

            # Check properties for constraints
            if isinstance(item, ast.FunctionDef) and item.decorator_list:
                for dec in item.decorator_list:
                    if isinstance(dec, ast.Name) and dec.id == "property":
                        # Property getter might enforce invariant
                        state_constraints.append(f"Property {item.name} has getter constraint")

        # Look for attributes initialized in __init__
        attributes = self._find_initialized_attributes(node)

        # Check if attributes are used in assertions (invariants)
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_invariants = self._find_assertion_invariants(item, attributes)
                invariants.extend(method_invariants)

        if invariants or state_constraints:
            confidence = "medium" if invariants else "low"
            self.class_invariants[node.name] = ClassInvariant(
                class_name=node.name,
                invariants=invariants,
                state_constraints=state_constraints,
                confidence=confidence,
            )

        self.current_class = None
        self.generic_visit(node)

    def _analyze_init_for_invariants(self, init_node: ast.FunctionDef) -> List[str]:
        """Analyze __init__ method for invariant patterns."""
        invariants: List[str] = []

        for stmt in init_node.body:
            # Look for assert statements on self attributes
            if isinstance(stmt, ast.Assert):
                condition = ast.unparse(stmt.test)
                if "self." in condition:
                    invariants.append(f"Init validates: {condition}")

            # Look for type checking
            if isinstance(stmt, ast.If):
                if isinstance(stmt.test, ast.Compare):
                    condition = ast.unparse(stmt.test)
                    if "isinstance" in condition and "self." in condition:
                        # Type check on self attribute
                        invariants.append(f"Type constraint in __init__: {condition}")

        return invariants

    def _find_initialized_attributes(self, class_node: ast.ClassDef) -> Set[str]:
        """Find attributes initialized in __init__."""
        attributes: Set[str] = set()

        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                for stmt in ast.walk(item):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                                if target.value.id == "self":
                                    attributes.add(target.attr)

        return attributes

    def _find_assertion_invariants(
        self,
        method_node: ast.FunctionDef,
        class_attributes: Set[str],
    ) -> List[str]:
        """Find assertion-based invariants in method."""
        invariants: List[str] = []

        for stmt in ast.walk(method_node):
            if isinstance(stmt, ast.Assert):
                condition = ast.unparse(stmt.test)
                # Check if assertion involves class attributes
                for attr in class_attributes:
                    if f"self.{attr}" in condition:
                        invariants.append(f"Invariant in {method_node.name}: {condition}")
                        break

        return invariants


class DataStructureInvariantDetector(ast.NodeVisitor):
    """Detect invariants in data structures."""

    def __init__(self) -> None:
        self.invariants: Dict[str, List[str]] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Analyze data structure class for invariants."""
        invariants: List[str] = []

        # Check for common data structure patterns
        # 1. Stack: push, pop, top operations
        # 2. Queue: enqueue, dequeue operations
        # 3. Binary tree: left, right, parent relationships

        methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]

        # Detect Stack-like structures
        if "push" in methods and "pop" in methods:
            invariants.append("Stack-like structure: pop returns most recently pushed item")

        # Detect Queue-like structures
        if "enqueue" in methods and "dequeue" in methods:
            invariants.append("Queue-like structure: FIFO ordering")

        # Detect Tree-like structures
        if "left" in methods or "right" in methods or "parent" in methods:
            invariants.append("Tree-like structure: has hierarchical relationships")

        # Detect Container-like structures
        if any(name in methods for name in ["add", "remove", "contains", "find"]):
            invariants.append("Container-like structure: maintains collection of items")

        if invariants:
            self.invariants[node.name] = invariants

        self.generic_visit(node)


def detect_loop_invariants(source_code: str) -> List[LoopInvariant]:
    """
    Detect loop invariants in source code.

    Args:
        source_code: Python source code

    Returns:
        List of LoopInvariant objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    detector = LoopInvariantDetector()
    detector.visit(tree)

    return detector.loop_invariants


def detect_class_invariants(
    source_code: str,
    classes: List[ClassInfo],
) -> Dict[str, ClassInvariant]:
    """
    Detect class invariants.

    Args:
        source_code: Python source code
        classes: List of classes to analyze

    Returns:
        Dict mapping class names to ClassInvariant objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {}

    detector = ClassInvariantDetector(source_code)
    detector.visit(tree)

    return detector.class_invariants


def detect_data_structure_invariants(source_code: str) -> Dict[str, List[str]]:
    """
    Detect invariants in data structures.

    Args:
        source_code: Python source code

    Returns:
        Dict mapping structure names to invariant descriptions
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {}

    detector = DataStructureInvariantDetector()
    detector.visit(tree)

    return detector.invariants


def verify_invariant_preservation(
    source_code: str,
    functions: List[FunctionInfo],
    invariants: Dict[str, List[str]],
) -> List[InvariantViolation]:
    """
    Verify that invariants are preserved across function calls.

    Args:
        source_code: Python source code
        functions: List of functions to check
        invariants: Dict of invariants to verify

    Returns:
        List of InvariantViolation objects
    """
    violations: List[InvariantViolation] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    # Check methods that might violate invariants
    for func in functions:
        # Only check methods (have . in name)
        if "." not in func.name:
            continue

        class_name = func.name.split(".")[0]
        if class_name not in invariants:
            continue

        # Find function node
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func.name:
                func_node = node
                break

        if not func_node:
            continue

        # Check for potential violations
        for child in ast.walk(func_node):
            # Direct assignment to self attributes could violate invariants
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Attribute):
                        if isinstance(target.value, ast.Name) and target.value.id == "self":
                            # Check if this is followed by an assert (validation)
                            has_validation = False
                            for sibling in func_node.body:
                                if isinstance(sibling, ast.Assert):
                                    has_validation = True
                                    break

                            if not has_validation:
                                violations.append(
                                    InvariantViolation(
                                        invariant_type="class",
                                        entity_name=func.name,
                                        location=f"{func.name}:{child.lineno}",
                                        severity="low",
                                        description=f"Direct assignment to {target.attr} without validation",
                                        suggestion="Add assert statement to verify invariant after assignment",
                                    )
                                )

    return violations


def generate_invariant_report(
    loop_invariants: List[LoopInvariant],
    class_invariants: Dict[str, ClassInvariant],
    data_structure_invariants: Dict[str, List[str]],
    violations: List[InvariantViolation],
) -> dict:
    """
    Generate invariant analysis report.

    Args:
        loop_invariants: Detected loop invariants
        class_invariants: Detected class invariants
        data_structure_invariants: Detected data structure invariants
        violations: Detected invariant violations

    Returns:
        Dict with summary and details
    """
    return {
        "summary": {
            "total_loop_invariants": len(loop_invariants),
            "total_class_invariants": len(class_invariants),
            "total_data_structure_invariants": len(data_structure_invariants),
            "total_violations": len(violations),
            "violations_by_severity": _count_by_severity(violations),
        },
        "loop_invariants": [
            {
                "type": inv.loop_type,
                "variable": inv.loop_variable,
                "line": inv.line_start,
                "invariants": inv.invariants,
            }
            for inv in loop_invariants
        ],
        "class_invariants": [
            {
                "class": name,
                "invariants": inv.invariants,
                "state_constraints": inv.state_constraints,
                "confidence": inv.confidence,
            }
            for name, inv in class_invariants.items()
        ],
        "data_structure_invariants": [
            {
                "structure": name,
                "invariants": invs,
            }
            for name, invs in data_structure_invariants.items()
        ],
        "violations": [
            {
                "type": v.invariant_type,
                "entity": v.entity_name,
                "location": v.location,
                "severity": v.severity,
                "description": v.description,
                "suggestion": v.suggestion,
            }
            for v in violations
        ],
    }


def _count_by_severity(violations: List[InvariantViolation]) -> Dict[str, int]:
    """Count violations by severity."""
    counts: Dict[str, int] = {}
    for v in violations:
        counts[v.severity] = counts.get(v.severity, 0) + 1
    return counts
