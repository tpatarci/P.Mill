# Program Mill (P.Mill) — Rigorous Program Verification

**Bulletproof software through externalized formal reasoning.**

## Vision

Program Mill applies the same rigorous, multi-stage verification approach that Epistemic Mill uses for propositional analysis, but for **code verification and optimization**.

Just as E.Mill creates an externalized self-check loop for logical claims, P.Mill creates an externalized verification loop for program correctness, security, and performance.

## Core Philosophy

**P.Mill does not "understand code better."** Instead, it builds an **EXTERNALIZED VERIFICATION FRAMEWORK** that systematically analyzes code through multiple formal lenses:

- **Structural Analysis**: AST, CFG, dependency graphs, complexity metrics
- **Formal Specification**: Preconditions, postconditions, invariants, contracts
- **Multi-Lens Verification**: Logic, security, performance, maintainability
- **Iterative Refinement**: Systematic debugging and optimization loops
- **Provable Guarantees**: Formal proofs or concrete counterexamples

## What Makes P.Mill Different

### Traditional Static Analysis
- Single-pass pattern matching
- Heuristic rules
- High false positive rate
- No formal guarantees

### P.Mill Approach
- Multi-stage verification pipeline
- Formal reasoning with LLMs as execution engines
- Iterative refinement loops
- Transparent, auditable reasoning
- Provable properties or concrete counterexamples

## The Pipeline

### Phase 0: Ingestion
- Parse source code into AST
- Build control flow graphs (CFG)
- Extract dependency graphs
- Compute complexity metrics

### Phase 1: Structural Analysis
- Identify complexity hotspots
- Map data flows and side effects
- Detect coupling and cohesion issues
- Classify code patterns and anti-patterns

### Phase 2: Formal Specification
- Extract/infer function contracts
- Identify invariants and assumptions
- Map security boundaries
- Trace resource lifecycles (files, memory, connections)

### Phase 3: Verification Loop
- **Logic Critic**: Correctness verification, prove invariants or find counterexamples
- **Security Critic**: OWASP top 10, injection points, auth/authz flows
- **Performance Critic**: Algorithmic complexity, memory leaks, optimization opportunities
- **Maintainability Critic**: Code smells, testability, documentation quality

### Phase 4: Synthesis & Repair
- Generate verified fixes
- Prove equivalence of optimizations
- Suggest refactorings with formal guarantees
- Produce comprehensive verification report

## Use Cases

### 1. Pre-Commit Verification
Run P.Mill on all changes before commit. Get formal verification that your changes:
- Don't introduce bugs
- Don't violate security contracts
- Don't degrade performance
- Maintain code quality standards

### 2. Legacy Code Analysis
Point P.Mill at legacy codebases:
- Extract implicit contracts and invariants
- Identify security vulnerabilities
- Find performance bottlenecks
- Generate modernization roadmap

### 3. Critical Path Verification
For mission-critical code paths:
- Prove correctness formally
- Verify error handling is complete
- Ensure resource cleanup
- Validate security boundaries

### 4. Optimization with Guarantees
Let P.Mill suggest optimizations:
- Prove equivalence before and after
- Measure actual performance impact
- Verify no side effects introduced
- Generate benchmarks automatically

## Tech Stack

- **Backend**: Python 3.11+, FastAPI (async)
- **Analysis**: AST parsing, static analysis, symbolic execution
- **LLM**: Anthropic Claude (formal reasoning), Cerebras (fast inference)
- **Storage**: SQLite for analysis results
- **Testing**: pytest with 100% fixture coverage

## Principles

1. **Formal Before Fast**: Correctness over speed
2. **Provable Claims**: Every assertion must be verified or proven
3. **Transparent Reasoning**: All verification steps externalized and auditable
4. **No Silent Failures**: Every issue found, every assumption stated
5. **Iteration Until Proof**: Multi-stage loops until formal guarantees achieved

## Quick Start

```bash
# Setup
cp .env.example .env
pip install -e .

# Analyze a Python file
python -m pmill analyze path/to/code.py

# Run verification suite
python -m pmill verify path/to/module/

# Full pipeline with optimization
python -m pmill optimize --verify path/to/code.py
```

## Comparison with E.Mill

| Aspect | E.Mill | P.Mill |
|--------|--------|--------|
| Domain | Propositional claims | Program code |
| Input | Natural language text | Source code |
| Analysis | Logical validity, evidence | Correctness, security, performance |
| Output | Structured argument analysis | Verification report, fixes, optimizations |
| Guarantee | Epistemic validity | Formal correctness proofs |

## Project Status

**Phase**: Initial Architecture (v0.1)

- [x] Vision and architecture defined
- [ ] Phase 0: Code ingestion and AST parsing
- [ ] Phase 1: Structural analysis pipeline
- [ ] Phase 2: Formal specification extraction
- [ ] Phase 3: Multi-critic verification loop
- [ ] Phase 4: Synthesis and repair
- [ ] Integration with CI/CD
- [ ] Multi-language support

## Contributing

P.Mill follows the same rigorous engineering standards as E.Mill:
- 100% test coverage with fixtures
- API-first design (no browser required)
- Formal documentation for all components
- Every feature must include adversarial test cases

See `CLAUDE.md` for detailed development guidelines.

## License

MIT License - See LICENSE file

## Related Projects

- **E.Mill** (Epistemic Mill): Rigorous propositional analysis
- Inspired by: formal methods, abstract interpretation, symbolic execution

---

**Built with the same rigor we verify.**
