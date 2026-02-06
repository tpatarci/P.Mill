"""Coupling analysis for Python code.

This module analyzes coupling between classes and modules:
- Afferent coupling (Ca): How many other classes depend on this class
- Efferent coupling (Ce): How many other classes this class depends on
- Instability (I): Ce / (Ca + Ce)
- God class detection: High efferent coupling + many methods
- Feature envy: Method that uses another class more than its own
- Inappropriate intimacy: Excessive access to another class's internals
"""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import structlog

from backend.models import ClassInfo, FunctionInfo

logger = structlog.get_logger()


# Thresholds for coupling analysis
DEFAULT_COUPLING_THRESHOLD = 10
DEFAULT_INSTABILITY_HIGH = 0.8
DEFAULT_INSTABILITY_LOW = 0.2
DEFAULT_GOD_CLASS_COUPLING = 8
DEFAULT_FEATURE_ENVY_THRESHOLD = 0.7  # 70% of accessed attributes are from other classes
DEFAULT_METHOD_COUPLING_THRESHOLD = 5


@dataclass
class ClassCoupling:
    """Coupling metrics for a single class."""

    class_name: str
    afferent_coupling: int = 0  # Ca: classes that depend on this class
    efferent_coupling: int = 0  # Ce: classes this class depends on
    instability: float = 0.0  # I = Ce / (Ca + Ce)
    dependencies: Set[str] = field(default_factory=set)  # Classes this class depends on
    dependents: Set[str] = field(default_factory=set)  # Classes that depend on this class


@dataclass
class GodClassInfo:
    """Information about a potential god class."""

    class_name: str
    severity: str
    reasons: List[str]
    efferent_coupling: int
    method_count: int
    suggestion: str


@dataclass
class FeatureEnvyInfo:
    """Information about a method with feature envy."""

    class_name: str
    method_name: str
    envied_class: str
    severity: str
    external_access_ratio: float
    suggestion: str


@dataclass
class IntimacyInfo:
    """Information about inappropriate intimacy between classes."""

    source_class: str
    target_class: str
    severity: str
    access_count: int
    suggestion: str


class CouplingAnalyzer(ast.NodeVisitor):
    """AST visitor to analyze coupling between classes."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.class_names: Set[str] = set()
        self.class_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.class_accesses: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.current_class: Optional[str] = None
        self.current_function: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class definition."""
        class_name = node.name
        self.class_names.add(class_name)
        self.current_class = class_name

        # Check base classes
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name and base_name in self.class_names:
                self.class_dependencies[class_name].add(base_name)

        # Visit body
        self.generic_visit(node)

        self.current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit a function definition."""
        old_function = self.current_function
        self.current_function = node.name

        # Check parameter types for class dependencies
        for param in node.args.args:
            if param.annotation:
                type_name = self._get_name(param.annotation)
                if type_name and type_name in self.class_names:
                    if self.current_class:
                        self.class_dependencies[self.current_class].add(type_name)

        # Check return type
        if node.returns:
            return_type = self._get_name(node.returns)
            if return_type and return_type in self.class_names:
                if self.current_class:
                    self.class_dependencies[self.current_class].add(return_type)

        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit an async function definition."""
        self.visit_FunctionDef(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit attribute access to track cross-class usage."""
        if self.current_class and self.current_function:
            # Get the object being accessed
            obj_name = self._get_name(node.value)
            if obj_name and obj_name in self.class_names and obj_name != self.current_class:
                # Track that current_class's method accesses obj_class's attributes
                self.class_accesses[self.current_class][obj_name] += 1

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call to track method invocation on other classes."""
        if self.current_class:
            func_name = self._get_name(node.func)
            if func_name:
                # Check if it's a method call on another class instance
                if "." in func_name:
                    parts = func_name.split(".")
                    if len(parts) >= 2:
                        obj_name = parts[0]
                        if obj_name in self.class_names and obj_name != self.current_class:
                            self.class_dependencies[self.current_class].add(obj_name)

        self.generic_visit(node)

    def _get_name(self, node: ast.AST) -> Optional[str]:
        """Extract name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Subscript):
            return self._get_name(node.value)
        return None


def analyze_coupling(
    source_code: str,
    classes: List[ClassInfo],
) -> Dict[str, ClassCoupling]:
    """
    Analyze coupling between classes in a module.

    Args:
        source_code: Python source code
        classes: List of ClassInfo objects

    Returns:
        Dict mapping class names to ClassCoupling metrics
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        logger.warning("coupling_parse_failed")
        return {}

    analyzer = CouplingAnalyzer(source_code)
    analyzer.visit(tree)

    # Build coupling metrics for each class
    class_names = {c.name for c in classes}
    coupling_map: Dict[str, ClassCoupling] = {}

    for cls in classes:
        deps = analyzer.class_dependencies.get(cls.name, set())
        # Only count dependencies within the analyzed module
        internal_deps = deps & class_names

        coupling = ClassCoupling(
            class_name=cls.name,
            efferent_coupling=len(internal_deps),
            dependencies=internal_deps,
        )
        coupling_map[cls.name] = coupling

    # Calculate afferent coupling (how many classes depend on this one)
    for cls_name, coupling in coupling_map.items():
        for dep_class in class_names:
            if dep_class != cls_name:
                if cls_name in coupling_map[dep_class].dependencies:
                    coupling.afferent_coupling += 1
                    coupling.dependents.add(dep_class)

    # Calculate instability for each class
    for coupling in coupling_map.values():
        total = coupling.afferent_coupling + coupling.efferent_coupling
        if total > 0:
            coupling.instability = coupling.efferent_coupling / total

    return coupling_map


def identify_god_classes(
    classes: List[ClassInfo],
    coupling_map: Dict[str, ClassCoupling],
    coupling_threshold: int = DEFAULT_GOD_CLASS_COUPLING,
    method_threshold: int = DEFAULT_METHOD_COUPLING_THRESHOLD,
) -> List[GodClassInfo]:
    """
    Identify potential god classes (high coupling + many methods).

    Args:
        classes: List of ClassInfo objects
        coupling_map: Class coupling metrics
        coupling_threshold: Efferent coupling threshold
        method_threshold: Method count threshold

    Returns:
        List of GodClassInfo for detected god classes
    """
    god_classes: List[GodClassInfo] = []

    for cls in classes:
        coupling = coupling_map.get(cls.name)
        method_count = len(cls.methods)
        reasons: List[str] = []

        # Check efferent coupling
        efferent = coupling.efferent_coupling if coupling else 0
        if efferent >= coupling_threshold:
            reasons.append(f"high efferent coupling ({efferent} dependencies)")

        # Check method count
        if method_count >= method_threshold:
            reasons.append(f"many methods ({method_count} methods)")

        if reasons:
            # Determine severity
            if efferent >= coupling_threshold * 2 or method_count >= method_threshold * 2:
                severity = "critical"
            elif efferent >= coupling_threshold * 1.5 or method_count >= method_threshold * 1.5:
                severity = "high"
            else:
                severity = "medium"

            god_classes.append(
                GodClassInfo(
                    class_name=cls.name,
                    severity=severity,
                    reasons=reasons,
                    efferent_coupling=efferent,
                    method_count=method_count,
                    suggestion=_get_god_class_suggestion(reasons),
                )
            )

    return god_classes


def detect_feature_envy(
    source_code: str,
    classes: List[ClassInfo],
    functions: List[FunctionInfo],
    threshold: float = DEFAULT_FEATURE_ENVY_THRESHOLD,
) -> List[FeatureEnvyInfo]:
    """
    Detect methods that prefer another class (feature envy).

    Args:
        source_code: Python source code
        classes: List of ClassInfo objects
        functions: List of FunctionInfo objects (including methods)
        threshold: Ratio threshold for feature envy

    Returns:
        List of FeatureEnvyInfo for detected feature envy
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    analyzer = CouplingAnalyzer(source_code)
    analyzer.visit(tree)

    feature_envy_list: List[FeatureEnvyInfo] = []

    for func in functions:
        # Only analyze methods (have class context)
        if "." not in func.name:
            continue

        # Extract class and method name
        parts = func.name.split(".")
        if len(parts) < 2:
            continue

        class_name = parts[0]
        method_name = ".".join(parts[1:])

        if class_name not in analyzer.class_accesses:
            continue

        # Count external accesses
        external_accesses: Dict[str, int] = {}
        total_external = 0
        total_internal = 0

        for target_class, count in analyzer.class_accesses.get(class_name, {}).items():
            if target_class != class_name:
                external_accesses[target_class] += count
                total_external += count
            else:
                total_internal += count

        # Check if method prefers another class
        if total_external > 0:
            total = total_internal + total_external
            external_ratio = total_external / total if total > 0 else 0

            if external_ratio >= threshold:
                # Find most accessed external class
                envied_class = max(external_accesses, key=external_accesses.get)

                severity = "high" if external_ratio >= 0.85 else "medium"

                feature_envy_list.append(
                    FeatureEnvyInfo(
                        class_name=class_name,
                        method_name=method_name,
                        envied_class=envied_class,
                        severity=severity,
                        external_access_ratio=external_ratio,
                        suggestion=_get_feature_envy_suggestion(envied_class),
                    )
                )

    return feature_envy_list


def detect_inappropriate_intimacy(
    coupling_map: Dict[str, ClassCoupling],
    intimacy_threshold: int = DEFAULT_COUPLING_THRESHOLD,
) -> List[IntimacyInfo]:
    """
    Detect inappropriate intimacy (excessive coupling between classes).

    Args:
        coupling_map: Class coupling metrics
        intimacy_threshold: Threshold for inappropriate intimacy

    Returns:
        List of IntimacyInfo for detected inappropriate intimacy
    """
    intimacy_list: List[IntimacyInfo] = []

    for source_class, coupling in coupling_map.items():
        for target_class in coupling.dependencies:
            # Check if target also depends heavily on source (bidirectional intimacy)
            target_coupling = coupling_map.get(target_class)
            if target_coupling and source_class in target_coupling.dependencies:
                # Both depend on each other - check for excessive coupling
                # Count the number of methods/fields accessed bidirectionally
                access_count = len(coupling.dependencies) + len(target_coupling.dependencies)

                if access_count >= intimacy_threshold:
                    severity = "high" if access_count >= intimacy_threshold * 2 else "medium"

                    intimacy_list.append(
                        IntimacyInfo(
                            source_class=source_class,
                            target_class=target_class,
                            severity=severity,
                            access_count=access_count,
                            suggestion=_get_intimacy_suggestion(source_class, target_class),
                        )
                    )

    return intimacy_list


def generate_coupling_report(
    coupling_map: Dict[str, ClassCoupling],
    god_classes: List[GodClassInfo],
    feature_envy: List[FeatureEnvyInfo],
    intimacy: List[IntimacyInfo],
) -> dict:
    """
    Generate a comprehensive coupling analysis report.

    Args:
        coupling_map: Class coupling metrics
        god_classes: Detected god classes
        feature_envy: Detected feature envy
        intimacy: Detected inappropriate intimacy

    Returns:
        Dict with summary and details
    """
    # Calculate summary statistics
    total_classes = len(coupling_map)
    avg_ca = sum(c.afferent_coupling for c in coupling_map.values()) / total_classes if total_classes > 0 else 0
    avg_ce = sum(c.efferent_coupling for c in coupling_map.values()) / total_classes if total_classes > 0 else 0
    avg_instability = sum(c.instability for c in coupling_map.values()) / total_classes if total_classes > 0 else 0

    # Count high instability classes
    high_instability = sum(1 for c in coupling_map.values() if c.instability > DEFAULT_INSTABILITY_HIGH)
    low_instability = sum(1 for c in coupling_map.values() if c.instability < DEFAULT_INSTABILITY_LOW)

    return {
        "summary": {
            "total_classes": total_classes,
            "avg_afferent_coupling": round(avg_ca, 2),
            "avg_efferent_coupling": round(avg_ce, 2),
            "avg_instability": round(avg_instability, 2),
            "high_instability_classes": high_instability,
            "low_instability_classes": low_instability,
        },
        "god_classes": [
            {
                "class": gc.class_name,
                "severity": gc.severity,
                "reasons": gc.reasons,
                "efferent_coupling": gc.efferent_coupling,
                "method_count": gc.method_count,
                "suggestion": gc.suggestion,
            }
            for gc in god_classes
        ],
        "feature_envy": [
            {
                "class": fe.class_name,
                "method": fe.method_name,
                "envied_class": fe.envied_class,
                "severity": fe.severity,
                "external_access_ratio": round(fe.external_access_ratio, 2),
                "suggestion": fe.suggestion,
            }
            for fe in feature_envy
        ],
        "inappropriate_intimacy": [
            {
                "source": ii.source_class,
                "target": ii.target_class,
                "severity": ii.severity,
                "access_count": ii.access_count,
                "suggestion": ii.suggestion,
            }
            for ii in intimacy
        ],
        "class_details": {
            name: {
                "afferent_coupling": c.afferent_coupling,
                "efferent_coupling": c.efferent_coupling,
                "instability": round(c.instability, 2),
                "dependencies": list(c.dependencies),
                "dependents": list(c.dependents),
            }
            for name, c in coupling_map.items()
        },
    }


def _get_god_class_suggestion(reasons: List[str]) -> str:
    """Get suggestion for god class refactoring."""
    if "many methods" in " ".join(reasons).lower():
        return "Consider splitting this class into smaller, more focused classes following Single Responsibility Principle."
    return "Consider reducing dependencies by using dependency injection, interfaces, or splitting into smaller classes."


def _get_feature_envy_suggestion(envied_class: str) -> str:
    """Get suggestion for feature envy refactoring."""
    return f"Consider moving this method to {envied_class} or using delegation patterns to reduce coupling."


def _get_intimacy_suggestion(source: str, target: str) -> str:
    """Get suggestion for inappropriate intimacy refactoring."""
    return f"Consider extracting a shared abstraction or mediator between {source} and {target} to reduce bidirectional coupling."
