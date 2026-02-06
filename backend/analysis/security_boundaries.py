"""Security boundary analysis for Python code.

This module identifies:
- Input boundaries (user input, network, files)
- Output boundaries (database, network, files)
- Privilege boundaries
- Data trust levels
"""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import structlog

from backend.models import ClassInfo, FunctionInfo

logger = structlog.get_logger()


# Known sources of untrusted input
UNTRUSTED_SOURCES = {
    "request",  # Flask/Django/etc HTTP request
    "flask.request",
    "HttpRequest",
    "WebRequest",
    "fastapi.Request",
    "starlette.request",
    "input",  # Built-in input()
    "sys.stdin",
    "os.environ",  # Environment variables (potentially untrusted)
    "argv",  # Command line arguments
    "getattr",
    "__getitem__",
}

# Known sink categories (where data flows)
SINK_CATEGORIES = {
    "database": ["execute", "executemany", "cursor.execute", "db.execute"],
    "network": ["requests.", "urllib.", "http.client", "socket.send", "socket.sendto"],
    "file": ["open(", "file.write", "Path.write", "os.remove", "os.unlink"],
    "command": ["os.system", "subprocess.call", "subprocess.run", "subprocess.Popen"],
    "eval": ["eval", "exec", "__import__"],
}


@dataclass
class SecurityBoundary:
    """A security boundary in the code."""

    boundary_type: str  # "input", "output", "privilege"
    entity_name: str
    line: int
    source_or_sink: str
    risk_level: str  # "low", "medium", "high", "critical"
    description: str
    suggestion: Optional[str] = None


@dataclass
class DataFlow:
    """A data flow path from source to sink."""

    source: str  # Where data originates
    sink: str  # Where data goes
    path: List[str]  # Functions in the path
    risk_level: str
    vulnerabilities: List[str]


@dataclass
class TrustLevel:
    """Trust level classification for data."""

    variable: str
    trust_level: str  # "untrusted", "validated", "trusted", "sanitized"
    validation_location: Optional[str] = None


class SecurityBoundaryAnalyzer(ast.NodeVisitor):
    """Analyze security boundaries in code."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.boundaries: List[SecurityBoundary] = []
        self.data_flows: List[DataFlow] = []
        self.trust_levels: Dict[str, TrustLevel] = {}
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None

        # Track where variables come from
        self.variable_sources: Dict[str, Set[str]] = defaultdict(set)

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

        # Check parameters for untrusted sources
        for arg in node.args.args:
            param_name = arg.arg
            # Check type hint for request types
            if arg.annotation:
                annotation = ast.unparse(arg.annotation)
                if any(source in annotation for source in ["Request", "HttpRequest", "WebRequest"]):
                    self.boundaries.append(
                        SecurityBoundary(
                            boundary_type="input",
                            entity_name=self.current_function,
                            line=node.lineno,
                            source_or_sink=param_name,
                            risk_level="high",
                            description=f"Parameter {param_name} comes from HTTP request",
                            suggestion="Validate and sanitize request input",
                        )
                    )
                    self.trust_levels[param_name] = TrustLevel(
                        variable=param_name,
                        trust_level="untrusted",
                    )

        # Check function body for boundary crossings
        self._analyze_function_body(node)

        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Analyze function call for security boundaries."""
        func_name = self._get_call_name(node)

        if not func_name:
            return

        # Check for input sources
        if self._is_untrusted_source(func_name):
            self.boundaries.append(
                SecurityBoundary(
                    boundary_type="input",
                    entity_name=self.current_function or "module",
                    line=node.lineno,
                    source_or_sink=func_name,
                    risk_level="medium",
                    description=f"Reads from untrusted source: {func_name}",
                    suggestion="Validate input from this source",
                )
            )

        # Check for output sinks
        sink_type, risk = self._check_sink(func_name)
        if sink_type:
            self.boundaries.append(
                SecurityBoundary(
                    boundary_type="output",
                    entity_name=self.current_function or "module",
                    line=node.lineno,
                    source_or_sink=func_name,
                    risk_level=risk,
                    description=f"Writes to {sink_type}: {func_name}",
                    suggestion="Validate/sanitize data before writing",
                )
            )

        # Check for eval/exec
        if func_name in ["eval", "exec", "__import__"]:
            self.boundaries.append(
                SecurityBoundary(
                    boundary_type="privilege",
                    entity_name=self.current_function or "module",
                    line=node.lineno,
                    source_or_sink=func_name,
                    risk_level="critical",
                    description=f"Uses dangerous function: {func_name}",
                    suggestion="Never use {func_name} with untrusted input",
                )
            )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Track variable assignments."""
        # Check if assignment is from untrusted source
        if isinstance(node.value, ast.Call):
            func_name = self._get_call_name(node.value)
            if func_name and self._is_untrusted_source(func_name):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.trust_levels[target.id] = TrustLevel(
                            variable=target.id,
                            trust_level="untrusted",
                        )
                        self.variable_sources[target.id].add(func_name)

        self.generic_visit(node)

    def _analyze_function_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Analyze function body for security patterns."""
        # Check for command injection patterns
        for child in ast.walk(node):
            if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Mod):
                # String concatenation with %
                if isinstance(child.right, ast.Tuple) or isinstance(child.right, ast.Name):
                    left = ast.unparse(child.left)
                    # Check if left might be user input
                    if "input" in left.lower() or any(f"self.{v}" in left for v in self.trust_levels.keys()):
                        self.boundaries.append(
                            SecurityBoundary(
                                boundary_type="output",
                                entity_name=self.current_function or "module",
                                line=child.lineno,
                                source_or_sink="string_format",
                                risk_level="high",
                                description="Potential format string injection",
                                suggestion="Use safe formatting methods",
                            )
                        )

    def _is_untrusted_source(self, func_name: str) -> bool:
        """Check if function is an untrusted source."""
        return any(source in func_name for source in UNTRUSTED_SOURCES)

    def _check_sink(self, func_name: str) -> Tuple[Optional[str], str]:
        """Check if function is a sink and return (type, risk_level)."""
        for sink_type, sinks in SINK_CATEGORIES.items():
            if any(sink in func_name for sink in sinks):
                if sink_type == "command":
                    return sink_type, "critical"
                elif sink_type == "eval":
                    return sink_type, "critical"
                else:
                    return sink_type, "medium"
        return None, "low"

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Get the name of a function call."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return ast.unparse(node.func)
        return None


def identify_input_boundaries(
    source_code: str,
    functions: List[FunctionInfo],
) -> List[SecurityBoundary]:
    """
    Identify input boundaries in source code.

    Args:
        source_code: Python source code
        functions: List of functions

    Returns:
        List of SecurityBoundary objects for inputs
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    analyzer = SecurityBoundaryAnalyzer(source_code)
    analyzer.visit(tree)

    return [b for b in analyzer.boundaries if b.boundary_type == "input"]


def identify_output_boundaries(
    source_code: str,
    functions: List[FunctionInfo],
) -> List[SecurityBoundary]:
    """
    Identify output boundaries in source code.

    Args:
        source_code: Python source code
        functions: List of functions

    Returns:
        List of SecurityBoundary objects for outputs
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    analyzer = SecurityBoundaryAnalyzer(source_code)
    analyzer.visit(tree)

    return [b for b in analyzer.boundaries if b.boundary_type == "output"]


def identify_privilege_boundaries(
    source_code: str,
    functions: List[FunctionInfo],
) -> List[SecurityBoundary]:
    """
    Identify privilege boundaries in source code.

    Args:
        source_code: Python source code
        functions: List of functions

    Returns:
        List of SecurityBoundary objects for privilege escalations
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    analyzer = SecurityBoundaryAnalyzer(source_code)
    analyzer.visit(tree)

    return [b for b in analyzer.boundaries if b.boundary_type == "privilege"]


def classify_trust_levels(
    source_code: str,
) -> Dict[str, TrustLevel]:
    """
    Classify trust levels for variables.

    Args:
        source_code: Python source code

    Returns:
        Dict mapping variable names to TrustLevel objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {}

    analyzer = SecurityBoundaryAnalyzer(source_code)
    analyzer.visit(tree)

    return analyzer.trust_levels


def generate_boundary_report(
    input_boundaries: List[SecurityBoundary],
    output_boundaries: List[SecurityBoundary],
    privilege_boundaries: List[SecurityBoundary],
    trust_levels: Dict[str, TrustLevel],
) -> dict:
    """
    Generate security boundary report.

    Args:
        input_boundaries: Detected input boundaries
        output_boundaries: Detected output boundaries
        privilege_boundaries: Detected privilege boundaries
        trust_levels: Variable trust levels

    Returns:
        Dict with summary and details
    """
    # Count by risk level
    risk_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for boundary in input_boundaries + output_boundaries + privilege_boundaries:
        risk_counts[boundary.risk_level] = risk_counts.get(boundary.risk_level, 0) + 1

    # Count trust levels
    trust_counts = defaultdict(int)
    for var, level in trust_levels.items():
        trust_counts[level.trust_level] += 1

    return {
        "summary": {
            "total_input_boundaries": len(input_boundaries),
            "total_output_boundaries": len(output_boundaries),
            "total_privilege_boundaries": len(privilege_boundaries),
            "total_boundaries": len(input_boundaries) + len(output_boundaries) + len(privilege_boundaries),
            "by_risk_level": risk_counts,
            "by_trust_level": dict(trust_counts),
        },
        "input_boundaries": [
            {
                "entity": b.entity_name,
                "line": b.line,
                "source": b.source_or_sink,
                "risk": b.risk_level,
                "description": b.description,
                "suggestion": b.suggestion,
            }
            for b in input_boundaries
        ],
        "output_boundaries": [
            {
                "entity": b.entity_name,
                "line": b.line,
                "sink": b.source_or_sink,
                "risk": b.risk_level,
                "description": b.description,
                "suggestion": b.suggestion,
            }
            for b in output_boundaries
        ],
        "privilege_boundaries": [
            {
                "entity": b.entity_name,
                "line": b.line,
                "operation": b.source_or_sink,
                "risk": b.risk_level,
                "description": b.description,
                "suggestion": b.suggestion,
            }
            for b in privilege_boundaries
        ],
        "trust_levels": [
            {
                "variable": var,
                "trust_level": level.trust_level,
            }
            for var, level in trust_levels.items()
        ],
    }
