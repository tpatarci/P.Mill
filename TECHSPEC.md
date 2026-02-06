# Program Mill — Technical Specification v0.1

## System Architecture

### Overview

Program Mill (P.Mill) is a multi-stage program verification pipeline that analyzes source code through formal lenses to provide rigorous correctness, security, and performance guarantees.

```
┌─────────────────────────────────────────────────────────────┐
│                    Program Mill Pipeline                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Phase 0: INGESTION                                          │
│  ├─ Parse source code → AST                                  │
│  ├─ Build control flow graph (CFG)                           │
│  ├─ Extract dependency graph                                 │
│  └─ Compute complexity metrics                               │
│                                                              │
│  Phase 1: STRUCTURAL ANALYSIS                                │
│  ├─ Identify complexity hotspots                             │
│  ├─ Detect coupling/cohesion issues                          │
│  ├─ Classify patterns and anti-patterns                      │
│  └─ Map data flows and side effects                          │
│                                                              │
│  Phase 2: FORMAL SPECIFICATION                               │
│  ├─ Extract/infer function contracts                         │
│  ├─ Identify invariants and assumptions                      │
│  ├─ Map security boundaries                                  │
│  └─ Trace resource lifecycles                                │
│                                                              │
│  Phase 3: VERIFICATION LOOP (Multi-Critic)                   │
│  ├─ Logic Critic (correctness)                               │
│  ├─ Security Critic (OWASP, injection, auth)                 │
│  ├─ Performance Critic (complexity, leaks)                   │
│  └─ Maintainability Critic (smells, testability)             │
│                                                              │
│  Phase 4: SYNTHESIS & REPAIR                                 │
│  ├─ Generate verified fixes                                  │
│  ├─ Prove equivalence of transformations                     │
│  ├─ Suggest optimizations with guarantees                    │
│  └─ Produce verification report                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Core Data Models

### Analysis Request

```python
class AnalysisRequest(BaseModel):
    """Request to analyze code."""
    code: str  # Source code to analyze
    language: str = "python"  # Programming language
    entry_point: Optional[str] = None  # Function/class to focus on
    verification_depth: Literal["quick", "standard", "rigorous"] = "standard"
    enable_synthesis: bool = True  # Generate fixes/optimizations
```

### AST Representation

```python
class ASTNode(BaseModel):
    """Unified AST node representation."""
    node_type: str  # function_def, class_def, if_stmt, etc.
    name: Optional[str]  # Name if applicable
    line_start: int
    line_end: int
    children: List['ASTNode'] = []
    attributes: Dict[str, Any] = {}  # Language-specific attributes

class CodeStructure(BaseModel):
    """Complete code structure."""
    ast: ASTNode
    functions: List[FunctionInfo]
    classes: List[ClassInfo]
    imports: List[ImportInfo]
    complexity_metrics: ComplexityMetrics
```

### Control Flow Graph

```python
class CFGNode(BaseModel):
    """Control flow graph node."""
    node_id: str
    node_type: Literal["entry", "exit", "statement", "branch", "loop", "call"]
    code_line: int
    statement: Optional[str]

class CFGEdge(BaseModel):
    """Control flow edge."""
    source: str  # node_id
    target: str  # node_id
    condition: Optional[str]  # For conditional branches

class ControlFlowGraph(BaseModel):
    """Complete CFG."""
    nodes: List[CFGNode]
    edges: List[CFGEdge]
    entry_node: str
    exit_nodes: List[str]
```

### Formal Specification

```python
class FunctionContract(BaseModel):
    """Formal contract for a function."""
    function_name: str
    preconditions: List[str]  # What must be true before call
    postconditions: List[str]  # What must be true after call
    invariants: List[str]  # What remains true throughout
    modifies: List[str]  # What state is modified
    raises: List[str]  # What exceptions can be raised
    complexity: str  # O(n), O(log n), etc.

class SecurityBoundary(BaseModel):
    """Security trust boundary."""
    boundary_type: Literal["input", "output", "privilege", "network"]
    location: str  # File:line or function name
    trusted_side: str  # Description
    untrusted_side: str  # Description
    validation_required: List[str]  # What must be validated
    current_validation: Optional[str]  # Current validation if any
```

### Verification Results

```python
class VerificationIssue(BaseModel):
    """A single verification issue."""
    issue_id: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: Literal["logic", "security", "performance", "maintainability"]
    title: str
    description: str
    location: str  # File:line or function name
    evidence: List[str]  # Concrete evidence (AST facts, dataflow, etc.)
    counterexample: Optional[str]  # If applicable
    suggested_fix: Optional[str]
    proof_of_fix: Optional[str]  # Why fix is correct

class VerificationReport(BaseModel):
    """Complete verification report."""
    analysis_id: str
    timestamp: datetime
    code_hash: str  # SHA256 of analyzed code
    issues: List[VerificationIssue]
    proven_properties: List[str]  # What was formally verified
    assumptions: List[str]  # What assumptions were made
    limitations: List[str]  # What was NOT verified
    metrics: Dict[str, Any]  # Performance, coverage, etc.
```

## Pipeline Steps

### Phase 0: Ingestion

**Input**: Raw source code (string)
**Output**: `CodeStructure` with AST, CFG, metrics

**Tools**:
- Python: `ast` module, `astroid` for advanced analysis
- CFG: Custom builder or `networkx`
- Metrics: `radon` for complexity, custom analyzers

**Verification Goal**: Parse is complete and accurate

### Phase 1: Structural Analysis

**Input**: `CodeStructure`
**Output**: List of structural observations

**Analysis Types**:
- Complexity hotspots (cyclomatic, cognitive)
- Coupling analysis (afferent/efferent coupling)
- Cohesion metrics (LCOM)
- Pattern detection (design patterns, anti-patterns)
- Dead code detection
- Duplicate code detection

**Verification Goal**: Structural properties are correctly classified

### Phase 2: Formal Specification

**Input**: `CodeStructure` + structural analysis
**Output**: `FunctionContract` for each function, `SecurityBoundary` list

**Extraction Methods**:
- Parse docstrings for explicit contracts
- Infer from assert statements
- Infer from raise statements
- Infer from type hints
- Use LLM to extract implicit contracts (with human review)

**Verification Goal**: Specifications are complete and consistent

### Phase 3: Verification Loop (Multi-Critic)

**Input**: Code + Specifications
**Output**: `VerificationReport`

#### Logic Critic
- Verify preconditions are checked before use
- Verify postconditions are established
- Verify invariants are maintained
- Check for null dereferences, array bounds, division by zero
- Verify error handling is complete

#### Security Critic
- OWASP Top 10 analysis
- SQL injection, XSS, command injection detection
- Authentication/authorization flow verification
- Secrets detection (hardcoded passwords, API keys)
- Input validation at boundaries
- Output encoding verification

#### Performance Critic
- Algorithmic complexity analysis
- Memory leak detection (unclosed resources)
- N+1 query detection
- Unnecessary allocations
- Caching opportunities

#### Maintainability Critic
- Code smell detection
- Test coverage gaps
- Documentation quality
- Naming conventions
- Dependency management

**Verification Goal**: All issues found, no false negatives (accept some false positives)

### Phase 4: Synthesis & Repair

**Input**: `VerificationReport` with issues
**Output**: List of verified fixes/optimizations

**Synthesis Process**:
1. Generate candidate fixes for each issue
2. Verify each fix preserves correctness
3. Prove equivalence (or document behavioral change)
4. Run tests to verify
5. Rank fixes by confidence

**Verification Goal**: Every suggested fix is proven safe

## LLM Integration

### LLM Roles

P.Mill uses LLMs for tasks that benefit from pattern recognition and semantic understanding, but ALWAYS with formal verification:

1. **Contract Inference**: LLM suggests implicit contracts, formal analysis verifies consistency
2. **Issue Description**: LLM generates human-readable descriptions of formal findings
3. **Fix Generation**: LLM generates candidate fixes, formal analysis proves correctness
4. **Security Pattern Recognition**: LLM identifies potential security issues, formal analysis confirms

### LLM Adapter

```python
class LLMAdapter(ABC):
    @abstractmethod
    async def infer_contract(self, function_ast: ASTNode) -> FunctionContract:
        """Infer function contract from AST."""
        pass

    @abstractmethod
    async def generate_fix(self, issue: VerificationIssue, context: CodeStructure) -> str:
        """Generate candidate fix for issue."""
        pass
```

### Prompt Structure

All prompts follow structured format:
1. **Task**: What to do
2. **Context**: Relevant code and analysis
3. **Constraints**: What must be preserved
4. **Format**: Expected output format (JSON schema)
5. **Examples**: Few-shot examples

## API Design

### REST API

```python
POST /api/v1/analyze
{
  "code": "def foo(x): return x + 1",
  "language": "python",
  "verification_depth": "standard"
}

Response:
{
  "analysis_id": "uuid",
  "status": "completed",
  "report": {...}
}

GET /api/v1/analyze/{analysis_id}
Response: Same as above

GET /api/v1/health
Response: {"status": "ok"}
```

### CLI

```bash
# Analyze single file
pmill analyze path/to/file.py

# Analyze module
pmill verify path/to/module/

# Optimize with verification
pmill optimize --verify path/to/file.py

# Generate report
pmill report --format html analysis_id
```

## Storage Schema

### SQLite Tables

```sql
CREATE TABLE analyses (
    id TEXT PRIMARY KEY,
    code_hash TEXT NOT NULL,
    code TEXT NOT NULL,
    language TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    report_json TEXT
);

CREATE TABLE issues (
    id TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL REFERENCES analyses(id),
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    location TEXT NOT NULL,
    evidence_json TEXT,
    suggested_fix TEXT,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
);

CREATE TABLE contracts (
    id TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL,
    function_name TEXT NOT NULL,
    contract_json TEXT NOT NULL,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
);
```

## Testing Strategy

### Unit Tests
- Each pipeline step tested in isolation
- Fixture-based with golden inputs/outputs
- No real LLM calls (use StubLLMAdapter)

### Integration Tests
- Full pipeline on sample codebases
- Verify end-to-end flow
- Check report format

### Adversarial Tests
- Malicious code inputs (injection attempts)
- Malformed AST
- Infinite loops
- Resource exhaustion

### Benchmark Suite
- Known vulnerable code samples (OWASP test suite)
- Performance benchmarks
- False positive rate tracking

## Security Considerations

1. **Sandboxing**: Never execute analyzed code directly
2. **Input Validation**: Assume all code input is malicious
3. **Resource Limits**: Timeout and memory limits on analysis
4. **Secrets**: Never log analyzed code (may contain secrets)
5. **Isolation**: Each analysis runs in isolated context

## Performance Targets

- **Small file** (<500 LOC): <10 seconds
- **Medium file** (500-2000 LOC): <60 seconds
- **Large file** (2000+ LOC): <5 minutes
- **Token budget**: Configurable, default 100K tokens per analysis

## Future Extensions

- Multi-language support (JavaScript, TypeScript, Go, Rust)
- IDE integration (LSP server)
- CI/CD integration (GitHub Actions, GitLab CI)
- Interactive refinement (human-in-the-loop)
- Theorem prover integration (Z3, Coq)
- Symbolic execution engine

---

**Version**: 0.1.0
**Last Updated**: 2026-02-06
**Status**: Architecture Phase
