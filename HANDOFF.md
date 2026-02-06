# P.Mill Phase 1 Implementation Handoff

**Date:** 2026-02-06
**Branch:** `feat/phase1-function-verification`
**Status:** Cards 1-2 Complete (28% of Phase 1), Cards 3-7 Ready to Implement
**Test Status:** 36 passing, 1 skipped (known limitation documented)

---

## Executive Summary

Phase 1 implementation is underway. The foundation is solid: AST parsing and fact extraction are complete with comprehensive test coverage. The architecture is working as designed. The next session should continue with Cards 3-7 following the established patterns.

---

## What's Been Completed

### ✅ Card 1: AST Parser + Function Extractor
**Location:** `backend/analysis/ast_parser.py`
**Tests:** `tests/test_ast_parser.py` (17 tests, 100% pass)
**Coverage:** 100% of ast_parser.py

**Capabilities:**
- Parse Python source code into AST
- Extract function inventory (top-level functions and methods)
- Handle async functions, regular functions, methods
- Extract: name, parameters, return types, docstrings, line ranges
- Get function source code by line range
- Find AST node by function name

**Key Functions:**
- `parse_python_file(source_code: str) -> tuple[ast.Module, List[FunctionInfo]]`
- `get_function_source(source_code: str, line_start: int, line_end: int) -> str`
- `get_function_ast_node(tree: ast.Module, function_name: str) -> Optional[ast.FunctionDef]`

**Design Notes:**
- Nested functions are detected but NOT analyzed (MVP simplification)
- Methods are extracted from classes with class context
- BUILTINS constant defined for builtin shadowing detection

---

### ✅ Card 2: Fact Extractor
**Location:** `backend/analysis/fact_extractor.py`
**Tests:** `tests/test_fact_extractor.py` (20 tests, 19 pass, 1 skipped)
**Coverage:** 95.38% of fact_extractor.py

**Capabilities - Tier 1 (Deterministic AST Facts):**
- Function metadata: name, qualified name, line range, is_method, is_async, class context
- Parameter analysis: names, type hints, defaults, mutable defaults detection
- Return type annotations
- Docstring presence and content
- Cyclomatic complexity (via radon)
- Lines of code (LOC)
- Decorators list
- Exception landscape: raised types, caught types
- None checks: which parameters have `is None` / `is not None` checks
- Type checks: which parameters have `isinstance()` checks
- Function calls made
- Bare except detection: `except:` without type
- Broad except detection: `except Exception:`
- Mutable default args: `def f(x=[])`
- Builtin shadowing: parameter names that shadow builtins
- Command execution: `os.system()`, `subprocess.call()`, etc.
- Command injection risk: command execution with f-strings
- Unreachable code detection (simplified)

**Key Functions:**
- `extract_function_facts(func_node, source_code, class_name) -> FunctionFacts`

**Known Limitations:**
1. **open() with context manager** (1 skipped test): Currently cannot distinguish `with open()` from bare `open()` due to single-pass visitor. Requires two-pass analysis or parent tracking. See test: `test_open_with_context_manager`. This is a false positive (marks safe code as unsafe). **FIX:** Implement parent node tracking in visitor or two-pass analysis.

2. **Return path analysis:** Currently simplified - just checks if any return exists. Full control flow analysis would be more accurate.

3. **Unreachable code:** Simplified detection - only catches obvious cases. Proper CFG would be better.

**Design Notes:**
- Uses radon for cyclomatic complexity (external dep, already in pyproject.toml)
- FunctionFacts model has 30+ fields - comprehensive coverage
- Visitor pattern for AST traversal
- All findings are deterministic (no LLM, no heuristics yet)

---

### ✅ Data Models Extended
**Location:** `backend/models/schemas.py`

**New Models Added:**
```python
class FindingTier(str, Enum):
    TIER1_DETERMINISTIC = "tier1_deterministic"
    TIER2_HEURISTIC = "tier2_heuristic"
    TIER3_SEMANTIC = "tier3_semantic"

class FindingConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INCONCLUSIVE = "inconclusive"

class ParameterInfo(BaseModel):
    name: str
    type_hint: Optional[str] = None
    has_default: bool = False
    default_is_mutable: bool = False

class FunctionFacts(BaseModel):
    # 30+ fields - see schemas.py lines 48-98

class LLMCheckMetadata(BaseModel):
    prompt_template: str
    model_id: str
    attempts: int
    first_response_parseable: bool
    raw_response: str
    parsed_answer: str
    cross_validation_result: Literal["confirmed", "no_data", "contradicted"]
```

**Extended Models:**
- `VerificationIssue` now has: `tier`, `confidence`, `llm_metadata`
- `VerificationReport` now has: `file_path`, `language`, `function_count`, `functions_analyzed`

---

## What's Next: Cards 3-7

### ⬜ Card 3: Pattern Checker (Tier 2)
**File to Create:** `backend/analysis/pattern_checker.py`
**Tests to Create:** `tests/test_pattern_checker.py`

**Task:** Implement 10 pattern checks from the plan's Tier 2 table:
1. Bare except (AST fact: `has_bare_except`)
2. Mutable default args (AST fact: `has_mutable_default_args`)
3. Resource leak risk (`uses_open_without_with`)
4. Command injection risk (`uses_command_execution` + `command_execution_has_fstring`)
5. Implicit None return (has return annotation but not all paths return)
6. Unreachable code (`has_unreachable_code`)
7. Giant function (LOC > 50 or complexity > 10)
8. Star imports (check AST for `from x import *`)
9. Broad exception (`has_broad_except`)
10. Shadow builtin (`shadows_builtin` list)

**Pattern:**
```python
def check_bare_except(facts: FunctionFacts) -> Optional[VerificationIssue]:
    if not facts.has_bare_except:
        return None

    return VerificationIssue(
        issue_id=f"{facts.qualified_name}:bare_except",
        severity="medium",
        category="maintainability",
        title="Bare except clause without exception type",
        description=f"Function {facts.function_name} uses bare 'except:' which catches all exceptions",
        location=f"{facts.function_name}:{facts.line_start}",
        tier=FindingTier.TIER2_HEURISTIC,
        confidence=FindingConfidence.HIGH,
        evidence=[f"AST analysis shows bare except clause"],
    )
```

**Each check is a pure function: `FunctionFacts -> Optional[VerificationIssue]`**

**Orchestration:**
```python
TIER2_CHECKS = [
    check_bare_except,
    check_mutable_defaults,
    check_resource_leak,
    # ... etc
]

def run_tier2_checks(facts: FunctionFacts) -> List[VerificationIssue]:
    issues = []
    for check in TIER2_CHECKS:
        issue = check(facts)
        if issue:
            issues.append(issue)
    return issues
```

**Test Pattern:** One fixture per pattern proving detection works.

---

### ⬜ Card 4: LLM Adapter
**Files to Create:**
- `backend/llm/adapter.py` - Abstract `LLMAdapter` + `StubLLMAdapter`
- `backend/llm/cerebras_adapter.py` - Real Cerebras implementation
- `tests/test_llm_adapter.py`

**Abstract Interface:**
```python
class LLMAdapter(ABC):
    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> str:
        """Get completion from LLM."""
        pass
```

**StubLLMAdapter for Tests:**
```python
class StubLLMAdapter(LLMAdapter):
    def __init__(self, canned_responses: dict[str, str]):
        self.responses = canned_responses
        self.call_count = 0

    async def complete(self, prompt: str, **kwargs) -> str:
        self.call_count += 1
        # Return canned response based on prompt content
        for key, response in self.responses.items():
            if key in prompt:
                return response
        return "UNCLEAR"
```

**CerebrasAdapter:**
- Use httpx for HTTP calls (already in deps)
- Implement retry logic with tenacity (already in deps)
- Config from settings: model, max_tokens, temperature, timeout, max_retries
- Handle API errors gracefully
- Return raw response string

**Config Updates Needed in `backend/config.py`:**
```python
# LLM Retry Configuration
llm_max_retries: int = 3
llm_timeout_seconds: int = 30
llm_max_tokens: int = 50  # For Tier 3 checks
llm_temperature: float = 0.0
```

---

### ⬜ Card 5: Null Safety Check (Tier 3)
**Files to Create:**
- `backend/llm/prompts.py` - Prompt templates
- `backend/llm/response_parser.py` - Parse LLM responses
- `tests/test_null_safety_check.py`

**Prompt Template (in prompts.py):**
```python
NULL_SAFETY_PROMPT = """You are checking Python functions for null safety issues.

EXAMPLES:
---
Function: def greet(name): return f"Hello, {name.upper()}"
Facts: Parameters=[name: no type hint]. No None checks in body. Calls: str.upper()
Question: Which parameters crash if None?
Answer: UNSAFE: name (calls .upper() on it without None check)
---
Function: def safe_greet(name):
    if name is None: return "Hello, stranger"
    return f"Hello, {name.upper()}"
Facts: Parameters=[name: no type hint]. Has None check for 'name'.
Question: Which parameters crash if None?
Answer: SAFE: all parameters handled
---

NOW ANALYZE:
Function:
```python
{function_code}
```
Facts: Parameters=[{param_list}]. {none_check_facts}. Calls: {call_list}
Question: Which parameters crash if None?
Answer:"""

def build_null_safety_prompt(facts: FunctionFacts) -> str:
    # Build prompt from template + facts
    pass
```

**Response Parser (in response_parser.py):**
```python
import re

def parse_null_safety_response(response: str) -> tuple[str, List[str]]:
    """
    Parse LLM response for null safety check.

    Returns:
        (answer_type, unsafe_params)
        answer_type: "SAFE" | "UNSAFE" | "UNCLEAR"
        unsafe_params: list of parameter names (empty if SAFE)
    """
    # Regex patterns to extract SAFE/UNSAFE/UNCLEAR
    # Handle garbled responses gracefully
    pass
```

**Test with StubLLMAdapter:**
```python
def test_null_safety_check_unsafe():
    stub = StubLLMAdapter({
        "greet": "UNSAFE: name (calls .upper() without None check)"
    })
    # ... test logic
```

---

### ⬜ Card 6: Cross-Validator
**File to Create:** `backend/pipeline/cross_validator.py`
**Tests to Create:** `tests/test_cross_validator.py`

**Task:** Implement cross-validation rules from plan (see table in original plan).

**Function Signature:**
```python
def cross_validate_null_safety(
    llm_answer: str,
    unsafe_params: List[str],
    facts: FunctionFacts
) -> tuple[FindingConfidence, str]:
    """
    Cross-validate LLM null safety claim against AST facts.

    Returns:
        (confidence, validation_result)
        confidence: HIGH | MEDIUM | LOW | INCONCLUSIVE
        validation_result: "confirmed" | "no_data" | "contradicted"
    """
    if llm_answer == "UNCLEAR":
        return FindingConfidence.INCONCLUSIVE, "no_data"

    if llm_answer == "SAFE":
        # Check if AST confirms all params have None checks
        if all(p.name in facts.has_none_checks for p in facts.parameters):
            return FindingConfidence.HIGH, "confirmed"
        else:
            return FindingConfidence.LOW, "contradicted"

    if llm_answer == "UNSAFE":
        # Check if AST confirms None checks are missing
        for param_name in unsafe_params:
            if param_name in facts.has_none_checks:
                return FindingConfidence.LOW, "contradicted"
        return FindingConfidence.HIGH, "confirmed"
```

**Test all 5 scenarios from the cross-validation rules table.**

---

### ⬜ Card 7: Pipeline Orchestrator + Report + CLI Integration
**Files to Create:**
- `backend/pipeline/analyzer.py` - Main orchestrator
- `backend/pipeline/report_generator.py` - JSON + text output
- `tests/test_pipeline_integration.py` - End-to-end tests

**Update:** `backend/cli.py` - Wire `pmill analyze` to real pipeline

**Orchestrator Pattern:**
```python
async def analyze_python_file(
    file_path: str,
    llm_adapter: Optional[LLMAdapter] = None
) -> VerificationReport:
    """
    Run full verification pipeline on a Python file.

    Steps:
    1. Read file
    2. Parse AST + extract functions
    3. For each function:
        a. Extract facts
        b. Run Tier 2 pattern checks
        c. Run Tier 3 LLM checks (if adapter provided)
        d. Cross-validate LLM findings
    4. Aggregate all issues
    5. Generate report
    """
    # Read source
    source_code = Path(file_path).read_text()

    # Parse
    tree, functions = parse_python_file(source_code)

    all_issues = []

    for func_info in functions:
        func_node = get_function_ast_node(tree, func_info.name)
        facts = extract_function_facts(func_node, source_code)

        # Tier 2
        tier2_issues = run_tier2_checks(facts)
        all_issues.extend(tier2_issues)

        # Tier 3 (if LLM available)
        if llm_adapter and facts.loc <= 200:
            try:
                tier3_issues = await run_null_safety_check(facts, llm_adapter)
                all_issues.extend(tier3_issues)
            except Exception as e:
                logger.warning("llm_check_failed", function=facts.function_name, error=str(e))

    # Generate report
    report = generate_report(file_path, source_code, functions, all_issues)
    return report
```

**CLI Integration (update backend/cli.py):**
```python
def analyze_file(file_path: str) -> None:
    """Analyze a single file."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    # Use stub adapter if no API key, real adapter if available
    adapter = None
    if settings.cerebras_api_key:
        adapter = CerebrasAdapter(settings)

    # Run analysis
    report = asyncio.run(analyze_python_file(str(path), adapter))

    # Print report
    print(format_report_text(report))

    # Optionally save JSON
    json_path = path.with_suffix('.pmill.json')
    json_path.write_text(report.model_dump_json(indent=2))
    print(f"\nFull report saved to: {json_path}")
```

**Report Generator:**
```python
def generate_report(...) -> VerificationReport:
    # Calculate code hash
    code_hash = hashlib.sha256(source_code.encode()).hexdigest()

    # Build report
    return VerificationReport(
        analysis_id=str(uuid.uuid4()),
        timestamp=datetime.now(),
        code_hash=code_hash,
        file_path=file_path,
        language="python",
        function_count=len(functions),
        functions_analyzed=[f.name for f in functions],
        issues=all_issues,
        proven_properties=[],  # TODO: Add proven properties
        assumptions=[],  # TODO: Add assumptions
        limitations=[],  # TODO: Add limitations
        metrics={}  # TODO: Add metrics
    )

def format_report_text(report: VerificationReport) -> str:
    # Pretty-print report for CLI
    pass
```

**End-to-End Test:**
```python
def test_analyze_conftest_file():
    """Test analyzing the conftest.py fixture file."""
    report = asyncio.run(analyze_python_file("tests/conftest.py"))

    # Should detect issues in vulnerable_code fixture
    assert any("command" in i.title.lower() for i in report.issues)
    assert any("injection" in i.description.lower() for i in report.issues)

    # Should analyze complex_code fixture
    assert "complex_function" in report.functions_analyzed

    # Should calculate complexity
    complex_issues = [i for i in report.issues if "complex" in i.location.lower()]
    assert len(complex_issues) > 0
```

---

## File Structure After Completion

```
backend/
├── analysis/
│   ├── __init__.py
│   ├── language_detector.py  [existing]
│   ├── ast_parser.py          [✅ DONE]
│   ├── fact_extractor.py      [✅ DONE]
│   └── pattern_checker.py     [TODO Card 3]
├── llm/
│   ├── __init__.py
│   ├── adapter.py             [TODO Card 4]
│   ├── cerebras_adapter.py    [TODO Card 4]
│   ├── prompts.py             [TODO Card 5]
│   └── response_parser.py     [TODO Card 5]
├── pipeline/
│   ├── __init__.py
│   ├── analyzer.py            [TODO Card 7]
│   ├── cross_validator.py     [TODO Card 6]
│   └── report_generator.py    [TODO Card 7]
├── models/
│   ├── __init__.py            [✅ UPDATED]
│   └── schemas.py             [✅ UPDATED]
├── cli.py                     [TODO Update Card 7]
├── config.py                  [TODO Update Card 4]
└── main.py                    [existing]

tests/
├── test_ast_parser.py         [✅ DONE - 17 tests]
├── test_fact_extractor.py     [✅ DONE - 19 pass, 1 skip]
├── test_pattern_checker.py    [TODO Card 3]
├── test_llm_adapter.py        [TODO Card 4]
├── test_null_safety_check.py  [TODO Card 5]
├── test_cross_validator.py    [TODO Card 6]
└── test_pipeline_integration.py [TODO Card 7]
```

---

## Running Tests

```bash
# All Phase 1 tests (currently 36 pass, 1 skip)
pytest tests/test_ast_parser.py tests/test_fact_extractor.py -v

# With coverage
pytest tests/ --cov=backend --cov-report=term-missing

# Run existing smoke tests (should still pass)
pytest tests/test_basic.py -v
```

---

## Git Commands for Next Session

```bash
# Continue work on this branch
git checkout feat/phase1-function-verification

# Pull latest if needed
git pull origin feat/phase1-function-verification

# When ready to merge to main
git checkout main
git merge feat/phase1-function-verification
git push origin main
```

---

## Dependencies Status

All required dependencies are in `pyproject.toml`:
- ✅ **Installed:** radon (for complexity)
- ✅ **Listed:** tenacity (for retry), httpx (for HTTP), anthropic (for API)
- ⚠️ **Not yet used:** tenacity, httpx, anthropic (needed for Cards 4-5)

**No new dependencies needed for Cards 3-7.**

---

## Key Design Decisions

1. **Single-pass AST visitor:** Fast but has limitations (e.g., open() detection). Acceptable for MVP.

2. **Tier-based findings:** Tier 1 (deterministic), Tier 2 (heuristic), Tier 3 (LLM-assisted). Clear separation.

3. **Confidence scoring:** HIGH = AST confirms, MEDIUM = LLM only, LOW = contradiction, INCONCLUSIVE = LLM failed.

4. **Stub adapter for tests:** NEVER call real LLM API in unit tests. Always use StubLLMAdapter.

5. **FunctionFacts as contract:** 30+ fields extracted once, reused by all checks. Single source of truth.

6. **Pattern checks as pure functions:** `FunctionFacts -> Optional[VerificationIssue]`. Easy to test, easy to add more.

7. **Graceful LLM degradation:** If LLM fails, pipeline continues with Tier 1+2 findings. Never block on LLM.

---

## Critical Reminders from CLAUDE.md

### MUST DO:
- ✅ Run tests before marking complete
- ✅ Use StubLLMAdapter in tests (NEVER real API)
- ✅ Track tasks in task list
- ✅ Commit on feature branch
- ⚠️ Get user approval before modifying verification logic (ask if uncertain)

### MUST NOT DO:
- ❌ Modify verification logic without approval
- ❌ Use real LLM API calls in unit tests
- ❌ Swallow exceptions silently
- ❌ Use magic strings for categorical values (use Enums)
- ❌ Claim verification without formal justification

### Verification Standard:
Every finding must include:
1. Formal statement (what is claimed)
2. Assumptions (preconditions)
3. Evidence (AST facts, LLM response, cross-validation)
4. Limitations (what is NOT proven)

---

## Estimation for Remaining Work

**Card 3 (Pattern Checker):** ~1-2 hours
- Straightforward - just convert AST facts to issues
- 10 pattern functions + orchestrator + 10 tests

**Card 4 (LLM Adapter):** ~2-3 hours
- Abstract interface: 30 min
- StubLLMAdapter: 30 min
- CerebrasAdapter with retry: 1 hour
- Tests: 1 hour

**Card 5 (Null Safety Check):** ~2-3 hours
- Prompt template: 30 min
- Response parser with regex: 1 hour
- Integration: 30 min
- Tests: 1 hour

**Card 6 (Cross-Validator):** ~1-2 hours
- Simple logic, well-specified in plan
- 5 test cases

**Card 7 (Pipeline + Report):** ~3-4 hours
- Orchestrator: 1 hour
- Report generator: 1 hour
- CLI integration: 30 min
- End-to-end tests: 1.5 hours

**Total:** ~9-14 hours for Cards 3-7

---

## Quick Start for Next Session

```bash
# 1. Checkout branch
git checkout feat/phase1-function-verification

# 2. Verify tests pass
pytest tests/test_ast_parser.py tests/test_fact_extractor.py -v

# 3. Start with Card 3
# Create: backend/analysis/pattern_checker.py
# Create: tests/test_pattern_checker.py
# Implement 10 pattern checks as pure functions

# 4. Run tests after each card
pytest tests/test_pattern_checker.py -v

# 5. Continue through Cards 4-7 in order
# (Card 6 depends on Cards 2+5, Card 7 depends on Cards 3+6)

# 6. Final verification
pytest tests/ -v
pmill analyze tests/conftest.py

# 7. Commit when complete
git add .
git commit -m "feat(phase1): complete function-level verification pipeline"
git push origin feat/phase1-function-verification
```

---

## Questions for Next Session

None - everything is well-specified in the original plan. Just follow the patterns established in Cards 1-2.

---

## Contact / Continuity

- **Original Plan:** See the plan document provided at start of session
- **CLAUDE.md:** Read this first - contains all mandatory guidelines
- **Test Fixtures:** `tests/conftest.py` has sample_python_code, vulnerable_code, complex_code
- **Expected Output:** By end of Phase 1, `pmill analyze file.py` should produce JSON + text report with Tier 1+2+3 findings

---

**Status:** Ready for next session to pick up at Card 3. Foundation is solid, tests are passing, architecture is proven.
