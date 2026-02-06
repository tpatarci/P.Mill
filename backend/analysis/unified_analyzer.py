"""Unified analyzer that integrates all analysis modules.

This is the main entry point for running all analyses on Python code.
"""

from __future__ import annotations

import ast
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

import structlog

from backend.analysis import (
    build_code_structure,
    classify_trust_levels,
    compute_cyclomatic_complexity,
    identify_input_boundaries,
    identify_output_boundaries,
    identify_privilege_boundaries,
)
from backend.analysis.contracts import Contract, extract_contracts
from backend.analysis.invariants import (
    InvariantViolation,
    detect_class_invariants,
    detect_loop_invariants,
    verify_invariant_preservation,
)
from backend.analysis.logic_critic import analyze_logic_issues
from backend.analysis.maintainability_critic import analyze_maintainability_issues
from backend.analysis.performance_critic import analyze_performance_issues
from backend.analysis.security_critic import analyze_security_issues
from backend.models import FunctionInfo

logger = structlog.get_logger()


@dataclass
class AnalysisResult:
    """Complete analysis result for a codebase."""

    analysis_id: str
    timestamp: datetime
    file_path: str
    language: str
    code_hash: str

    # Structure analysis
    structure: Any = None

    # Complexity metrics
    complexity_metrics: Dict[str, Any] = field(default_factory=dict)

    # Issues found by critics
    logic_issues: List[Dict[str, Any]] = field(default_factory=list)
    security_issues: List[Dict[str, Any]] = field(default_factory=list)
    performance_issues: List[Dict[str, Any]] = field(default_factory=list)
    maintainability_issues: List[Dict[str, Any]] = field(default_factory=list)

    # Contract and invariant analysis
    contracts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    invariants: List[Dict[str, Any]] = field(default_factory=list)

    # Security boundaries
    input_boundaries: List[Dict[str, Any]] = field(default_factory=list)
    output_boundaries: List[Dict[str, Any]] = field(default_factory=list)
    privilege_boundaries: List[Dict[str, Any]] = field(default_factory=list)
    trust_levels: Dict[str, str] = field(default_factory=dict)

    # Patterns detected
    design_patterns: List[Dict[str, Any]] = field(default_factory=list)

    # Summary
    summary: Dict[str, Any] = field(default_factory=dict)


class UnifiedAnalyzer:
    """
    Unified analyzer that runs all analysis modules.

    This is the main entry point for analyzing Python code.
    """

    def __init__(
        self,
        skip_patterns: bool = False,
        skip_contracts: bool = False,
        skip_invariants: bool = False,
    ) -> None:
        """
        Initialize the unified analyzer.

        Args:
            skip_patterns: Skip design pattern detection (slower)
            skip_contracts: Skip contract analysis
            skip_invariants: Skip invariant analysis
        """
        self.skip_patterns = skip_patterns
        self.skip_contracts = skip_contracts
        self.skip_invariants = skip_invariants

    def analyze(
        self,
        source_code: str,
        file_path: str = "unknown.py",
    ) -> AnalysisResult:
        """
        Run complete analysis on source code.

        Args:
            source_code: Python source code to analyze
            file_path: Path to the source file (for reporting)

        Returns:
            Complete AnalysisResult
        """
        analysis_id = str(uuid.uuid4())
        timestamp = datetime.now()
        code_hash = hashlib.sha256(source_code.encode()).hexdigest()

        logger.info(
            "starting_unified_analysis",
            analysis_id=analysis_id,
            file_path=file_path,
        )

        result = AnalysisResult(
            analysis_id=analysis_id,
            timestamp=timestamp,
            file_path=file_path,
            language="python",
            code_hash=code_hash,
        )

        try:
            # Parse code structure
            result.structure = build_code_structure(source_code)
            functions = result.structure.functions if result.structure else []

            # Run all analyses
            result.complexity_metrics = self._analyze_complexity(source_code, functions)
            result.logic_issues = self._analyze_logic(source_code, functions)
            result.security_issues = self._analyze_security(source_code, functions)
            result.performance_issues = self._analyze_performance(source_code, functions)
            result.maintainability_issues = self._analyze_maintainability(source_code, functions)

            if not self.skip_contracts:
                result.contracts = self._analyze_contracts(source_code)

            if not self.skip_invariants:
                result.invariants = self._analyze_invariants(source_code, functions)

            # Security boundary analysis
            result.input_boundaries, result.output_boundaries, result.privilege_boundaries, result.trust_levels = (
                self._analyze_security_boundaries(source_code, functions)
            )

            if not self.skip_patterns:
                result.design_patterns = self._analyze_patterns(source_code)

            # Generate summary
            result.summary = self._generate_summary(result)

            logger.info(
                "analysis_complete",
                analysis_id=analysis_id,
                total_issues=result.summary.get("total_issues", 0),
            )

        except SyntaxError as e:
            logger.warning("syntax_error", file_path=file_path, error=str(e))
            result.summary = {"error": "Syntax error in source code"}

        except Exception as e:
            logger.error("analysis_error", file_path=file_path, error=str(e))
            result.summary = {"error": str(e)}

        return result

    def _analyze_complexity(
        self,
        source_code: str,
        functions: List[FunctionInfo],
    ) -> Dict[str, Any]:
        """Analyze code complexity."""
        metrics = {
            "total_functions": len(functions),
            "functions_analyzed": 0,
            "avg_cyclomatic_complexity": 0,
            "high_complexity_functions": [],
        }

        if not functions:
            return metrics

        total_cc = 0
        for func in functions:
            try:
                cc = compute_cyclomatic_complexity(source_code)
                if isinstance(cc, dict):
                    # Take first CC value if available
                    for name, value in cc.items():
                        if isinstance(value, int):
                            total_cc += value
                            metrics["functions_analyzed"] += 1

                            if value > 10:
                                metrics["high_complexity_functions"].append({
                                    "name": name,
                                    "complexity": value,
                                })
                            break
            except Exception:
                pass

        if metrics["functions_analyzed"] > 0:
            metrics["avg_cyclomatic_complexity"] = total_cc / metrics["functions_analyzed"]

        return metrics

    def _analyze_logic(
        self,
        source_code: str,
        functions: List[FunctionInfo],
    ) -> List[Dict[str, Any]]:
        """Run logic critic analysis."""
        issues = analyze_logic_issues(source_code, functions)
        return [
            {
                "type": issue.issue_type,
                "function": issue.function_name,
                "line": issue.line,
                "severity": issue.severity,
                "description": issue.description,
                "suggestion": issue.suggestion,
            }
            for issue in issues
        ]

    def _analyze_security(
        self,
        source_code: str,
        functions: List[FunctionInfo],
    ) -> List[Dict[str, Any]]:
        """Run security critic analysis."""
        issues = analyze_security_issues(source_code, functions)
        return [
            {
                "type": issue.vuln_type,
                "function": issue.function_name,
                "line": issue.line,
                "severity": issue.severity,
                "description": issue.description,
                "suggestion": issue.suggestion,
            }
            for issue in issues
        ]

    def _analyze_performance(
        self,
        source_code: str,
        functions: List[FunctionInfo],
    ) -> List[Dict[str, Any]]:
        """Run performance critic analysis."""
        issues = analyze_performance_issues(source_code, functions)
        return [
            {
                "type": issue.issue_type,
                "function": issue.function_name,
                "line": issue.line,
                "severity": issue.severity,
                "description": issue.description,
                "suggestion": issue.suggestion,
            }
            for issue in issues
        ]

    def _analyze_maintainability(
        self,
        source_code: str,
        functions: List[FunctionInfo],
    ) -> List[Dict[str, Any]]:
        """Run maintainability critic analysis."""
        issues = analyze_maintainability_issues(source_code, functions)
        return [
            {
                "type": issue.issue_type,
                "function": issue.function_name,
                "line": issue.line,
                "severity": issue.severity,
                "description": issue.description,
                "suggestion": issue.suggestion,
            }
            for issue in issues
        ]

    def _analyze_contracts(
        self,
        source_code: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Run contract analysis."""
        contracts = extract_contracts(source_code)
        return {
            name: {
                "preconditions": c.preconditions,
                "postconditions": c.postconditions,
                "raises": c.raises,
                "return_type": c.return_type,
            }
            for name, c in contracts.items()
        }

    def _analyze_invariants(
        self,
        source_code: str,
        functions: List[FunctionInfo],
    ) -> List[Dict[str, Any]]:
        """Run invariant analysis."""
        from backend.models import ClassInfo

        # Detect loop invariants
        loop_invs = detect_loop_invariants(source_code)

        # Detect class invariants - need to extract classes first
        try:
            tree = ast.parse(source_code)
            classes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(ClassInfo(
                        name=node.name,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        bases=[ast.unparse(b) for b in node.bases],
                        methods=[m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                    ))
            class_invs = detect_class_invariants(source_code, classes)
        except Exception:
            class_invs = {}

        invariants = []
        for inv in loop_invs:
            invariants.append({
                "type": "loop_invariant",
                "loop_type": inv.loop_type,
                "loop_variable": inv.loop_variable,
                "line": inv.line_start,
                "invariants": inv.invariants,
            })

        for name, inv in class_invs.items():
            invariants.append({
                "type": "class_invariant",
                "class": name,
                "invariant": inv.invariant,
            })

        return invariants

    def _analyze_security_boundaries(
        self,
        source_code: str,
        functions: List[FunctionInfo],
    ) -> tuple:
        """Analyze security boundaries."""
        input_bounds = identify_input_boundaries(source_code, functions)
        output_bounds = identify_output_boundaries(source_code, functions)
        privilege_bounds = identify_privilege_boundaries(source_code, functions)
        trust_levels = classify_trust_levels(source_code)

        return (
            [
                {
                    "entity": b.entity_name,
                    "line": b.line,
                    "source": b.source_or_sink,
                    "risk": b.risk_level,
                }
                for b in input_bounds
            ],
            [
                {
                    "entity": b.entity_name,
                    "line": b.line,
                    "sink": b.source_or_sink,
                    "risk": b.risk_level,
                }
                for b in output_bounds
            ],
            [
                {
                    "entity": b.entity_name,
                    "line": b.line,
                    "operation": b.source_or_sink,
                    "risk": b.risk_level,
                }
                for b in privilege_bounds
            ],
            {var: level.trust_level for var, level in trust_levels.items()},
        )

    def _analyze_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Analyze design patterns."""
        from backend.analysis.patterns import detect_design_patterns

        # Need to extract classes first
        try:
            tree = ast.parse(source_code)
            classes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    from backend.models import ClassInfo
                    classes.append(ClassInfo(
                        name=node.name,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        bases=[ast.unparse(b) for b in node.bases],
                        methods=[m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                    ))

            patterns = detect_design_patterns(source_code, classes)
        except Exception:
            patterns = []

        return [
            {
                "pattern": p.pattern_name,
                "location": p.location,
                "confidence": p.confidence,
            }
            for p in patterns
        ]

    def _generate_summary(self, result: AnalysisResult) -> Dict[str, Any]:
        """Generate summary of all findings."""
        total_issues = (
            len(result.logic_issues) +
            len(result.security_issues) +
            len(result.performance_issues) +
            len(result.maintainability_issues)
        )

        severity_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

        for issue in (
            result.logic_issues +
            result.security_issues +
            result.performance_issues +
            result.maintainability_issues
        ):
            sev = issue.get("severity", "low")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        functions_count = 0
        classes_count = 0
        if result.structure:
            functions_count = len(result.structure.functions) if result.structure.functions else 0
            classes_count = len(result.structure.classes) if result.structure.classes else 0

        return {
            "total_issues": total_issues,
            "by_severity": severity_counts,
            "by_category": {
                "logic": len(result.logic_issues),
                "security": len(result.security_issues),
                "performance": len(result.performance_issues),
                "maintainability": len(result.maintainability_issues),
            },
            "functions_count": functions_count,
            "classes_count": classes_count,
        }


def analyze_code(
    source_code: str,
    file_path: str = "unknown.py",
    skip_patterns: bool = False,
    skip_contracts: bool = False,
    skip_invariants: bool = False,
) -> AnalysisResult:
    """
    Analyze Python code with all available critics.

    Args:
        source_code: Python source code
        file_path: Path to source file
        skip_patterns: Skip pattern detection (slower)
        skip_contracts: Skip contract analysis
        skip_invariants: Skip invariant analysis

    Returns:
        Complete AnalysisResult
    """
    analyzer = UnifiedAnalyzer(
        skip_patterns=skip_patterns,
        skip_contracts=skip_contracts,
        skip_invariants=skip_invariants,
    )
    return analyzer.analyze(source_code, file_path)
