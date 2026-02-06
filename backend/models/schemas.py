"""Pydantic schemas for Program Mill data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AnalysisStatus(str, Enum):
    """Status of an analysis."""

    PENDING = "pending"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    VERIFYING = "verifying"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisRequest(BaseModel):
    """Request to analyze code."""

    code: str = Field(..., description="Source code to analyze")
    language: Optional[str] = Field(
        default=None,
        description="Programming language (auto-detected if not provided)"
    )
    filename: Optional[str] = Field(
        default=None,
        description="Filename for extension-based language detection"
    )
    entry_point: Optional[str] = Field(
        default=None, description="Function/class to focus on"
    )
    verification_depth: Literal["quick", "standard", "rigorous"] = Field(
        default="standard", description="Depth of verification"
    )
    enable_synthesis: bool = Field(
        default=True, description="Generate fixes/optimizations"
    )


class ASTNode(BaseModel):
    """Unified AST node representation."""

    node_type: str = Field(..., description="Type of AST node")
    name: Optional[str] = Field(default=None, description="Name if applicable")
    line_start: int = Field(..., description="Starting line number")
    line_end: int = Field(..., description="Ending line number")
    children: List["ASTNode"] = Field(default_factory=list, description="Child nodes")
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Language-specific attributes"
    )


class FunctionInfo(BaseModel):
    """Information about a function."""

    name: str
    line_start: int
    line_end: int
    parameters: List[str]
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    complexity: int = 0


class ClassInfo(BaseModel):
    """Information about a class."""

    name: str
    line_start: int
    line_end: int
    methods: List[str]
    bases: List[str] = Field(default_factory=list)


class ImportInfo(BaseModel):
    """Information about an import."""

    module: str
    names: List[str]
    line: int


class ComplexityMetrics(BaseModel):
    """Code complexity metrics."""

    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    lines_of_code: int = 0
    maintainability_index: float = 0.0


class CodeStructure(BaseModel):
    """Complete code structure."""

    ast: ASTNode
    functions: List[FunctionInfo] = Field(default_factory=list)
    classes: List[ClassInfo] = Field(default_factory=list)
    imports: List[ImportInfo] = Field(default_factory=list)
    complexity_metrics: ComplexityMetrics = Field(default_factory=ComplexityMetrics)


class CFGNode(BaseModel):
    """Control flow graph node."""

    node_id: str
    node_type: Literal["entry", "exit", "statement", "branch", "loop", "call"]
    code_line: int
    statement: Optional[str] = None


class CFGEdge(BaseModel):
    """Control flow edge."""

    source: str = Field(..., description="Source node_id")
    target: str = Field(..., description="Target node_id")
    condition: Optional[str] = Field(
        default=None, description="Condition for conditional branches"
    )


class ControlFlowGraph(BaseModel):
    """Complete CFG."""

    nodes: List[CFGNode]
    edges: List[CFGEdge]
    entry_node: str
    exit_nodes: List[str]


class FunctionContract(BaseModel):
    """Formal contract for a function."""

    function_name: str
    preconditions: List[str] = Field(
        default_factory=list, description="What must be true before call"
    )
    postconditions: List[str] = Field(
        default_factory=list, description="What must be true after call"
    )
    invariants: List[str] = Field(
        default_factory=list, description="What remains true throughout"
    )
    modifies: List[str] = Field(
        default_factory=list, description="What state is modified"
    )
    raises: List[str] = Field(
        default_factory=list, description="What exceptions can be raised"
    )
    complexity: str = Field(default="O(1)", description="Algorithmic complexity")


class SecurityBoundary(BaseModel):
    """Security trust boundary."""

    boundary_type: Literal["input", "output", "privilege", "network"]
    location: str = Field(..., description="File:line or function name")
    trusted_side: str
    untrusted_side: str
    validation_required: List[str] = Field(
        default_factory=list, description="What must be validated"
    )
    current_validation: Optional[str] = Field(
        default=None, description="Current validation if any"
    )


class VerificationIssue(BaseModel):
    """A single verification issue."""

    issue_id: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: Literal["logic", "security", "performance", "maintainability"]
    title: str
    description: str
    location: str = Field(..., description="File:line or function name")
    evidence: List[str] = Field(
        default_factory=list, description="Concrete evidence (AST facts, dataflow, etc.)"
    )
    counterexample: Optional[str] = Field(default=None, description="If applicable")
    suggested_fix: Optional[str] = None
    proof_of_fix: Optional[str] = Field(
        default=None, description="Why fix is correct"
    )


class VerificationReport(BaseModel):
    """Complete verification report."""

    analysis_id: str
    timestamp: datetime
    code_hash: str = Field(..., description="SHA256 of analyzed code")
    issues: List[VerificationIssue] = Field(default_factory=list)
    proven_properties: List[str] = Field(
        default_factory=list, description="What was formally verified"
    )
    assumptions: List[str] = Field(
        default_factory=list, description="What assumptions were made"
    )
    limitations: List[str] = Field(
        default_factory=list, description="What was NOT verified"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Performance, coverage, etc."
    )
