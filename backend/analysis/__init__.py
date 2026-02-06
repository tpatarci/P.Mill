"""Code analysis modules for Program Mill."""

from .language_detector import LanguageDetector, detect_language
from .ast_parser import (
    BUILTINS,
    ASTNodeBuilder,
    build_code_structure,
    get_function_ast_node,
    get_function_source,
    parse_python_file,
)
from .complexity import (
    compute_cyclomatic_complexity,
    compute_cognitive_complexity,
    compute_maintainability_index,
    enrich_function_with_complexity,
)
from .cfg import CFGBuilder, visualize_cfg_dot
from .dependency import DependencyGraph, find_unused_imports
from .complexity_hotspots import analyze_function_hotspots, analyze_class_hotspots
from .coupling import CouplingAnalyzer, identify_god_classes, detect_feature_envy
from .patterns import (
    PatternMatch,
    AntiPatternMatch,
    generate_pattern_report,
)
from .contracts import Contract, extract_contracts, validate_contracts
from .llm_contracts import ContractInference
from .invariants import (
    LoopInvariant,
    ClassInvariant,
    InvariantViolation,
    detect_loop_invariants,
    detect_class_invariants,
    verify_invariant_preservation,
    generate_invariant_report,
)
from .security_boundaries import (
    SecurityBoundary,
    identify_input_boundaries,
    identify_output_boundaries,
    identify_privilege_boundaries,
    classify_trust_levels,
)
from .logic_critic import LogicCritic, analyze_logic_issues
from .security_critic import SecurityCritic, analyze_security_issues
from .performance_critic import PerformanceCritic, analyze_performance_issues
from .maintainability_critic import MaintainabilityCritic, analyze_maintainability_issues
from .unified_analyzer import AnalysisResult, UnifiedAnalyzer, analyze_code

__all__ = [
    # Language detection
    "LanguageDetector",
    "detect_language",
    # AST parsing
    "BUILTINS",
    "ASTNodeBuilder",
    "build_code_structure",
    "get_function_ast_node",
    "get_function_source",
    "parse_python_file",
    # Complexity analysis
    "compute_cyclomatic_complexity",
    "compute_cognitive_complexity",
    "compute_maintainability_index",
    "enrich_function_with_complexity",
    # Control flow
    "CFGBuilder",
    "visualize_cfg_dot",
    # Dependency analysis
    "DependencyGraph",
    "find_unused_imports",
    # Complexity hotspots
    "analyze_function_hotspots",
    "analyze_class_hotspots",
    # Coupling
    "CouplingAnalyzer",
    "identify_god_classes",
    "detect_feature_envy",
    # Patterns
    "PatternMatch",
    "AntiPatternMatch",
    "generate_pattern_report",
    # Contracts
    "Contract",
    "extract_contracts",
    "validate_contracts",
    "ContractInference",
    # Invariants
    "LoopInvariant",
    "ClassInvariant",
    "InvariantViolation",
    "detect_loop_invariants",
    "detect_class_invariants",
    "verify_invariant_preservation",
    "generate_invariant_report",
    # Security boundaries
    "SecurityBoundary",
    "identify_input_boundaries",
    "identify_output_boundaries",
    "identify_privilege_boundaries",
    "classify_trust_levels",
    # Critics
    "LogicCritic",
    "analyze_logic_issues",
    "SecurityCritic",
    "analyze_security_issues",
    "PerformanceCritic",
    "analyze_performance_issues",
    "MaintainabilityCritic",
    "analyze_maintainability_issues",
    # Unified analysis
    "AnalysisResult",
    "UnifiedAnalyzer",
    "analyze_code",
]
