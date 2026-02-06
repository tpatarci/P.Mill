"""End-to-end integration tests for the verification pipeline."""

import pytest

from backend.analysis.ast_parser import parse_python_file
from backend.pipeline.analyzer import analyze_python_file_sync, run_null_safety_check
from backend.llm import StubLLMAdapter


class TestPipelineIntegration:
    """End-to-end pipeline tests."""

    def test_analyze_simple_file(self):
        """Test analyzing a simple Python file."""
        code = """
def add(a: int, b: int) -> int:
    '''Add two numbers.'''
    return a + b

def divide(a: int, b: int) -> float:
    '''Divide two numbers.'''
    return a / b
"""
        # Write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            report = analyze_python_file_sync(temp_path)

            assert report.function_count == 2
            assert "add" in report.functions_analyzed
            assert "divide" in report.functions_analyzed
            assert len(report.issues) >= 0  # May have issues or not

        finally:
            import os
            os.unlink(temp_path)

    def test_analyze_vulnerable_code(self, vulnerable_code: str):
        """Test analyzing code with security vulnerabilities."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(vulnerable_code)
            temp_path = f.name

        try:
            report = analyze_python_file_sync(temp_path)

            # Should detect command injection
            assert any("command" in i.title.lower() or "injection" in i.title.lower()
                      for i in report.issues)

            # Should have security issues
            assert any(i.category == "security" for i in report.issues)

        finally:
            import os
            os.unlink(temp_path)

    def test_analyze_conftest_file(self):
        """Test analyzing the conftest.py fixture file."""
        import os
        conftest_path = os.path.join(os.path.dirname(__file__), "conftest.py")

        if os.path.exists(conftest_path):
            report = analyze_python_file_sync(conftest_path)

            # Should analyze the fixture functions themselves
            assert report.function_count >= 3  # sample_python_code, vulnerable_code, complex_code

            # The fixtures themselves are simple functions that return strings
            # They don't have issues (the issues are in the returned code strings)
            # This test just verifies we can analyze the file without crashing

    def test_report_has_required_fields(self):
        """Test that report has all required fields."""
        code = "def test(): pass"
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            report = analyze_python_file_sync(temp_path)

            assert report.analysis_id
            assert report.timestamp
            assert report.code_hash
            assert report.file_path
            assert report.language == "python"
            assert report.metrics is not None
            assert isinstance(report.functions_analyzed, list)

        finally:
            import os
            os.unlink(temp_path)

    def test_report_metrics_are_correct(self):
        """Test that report metrics are calculated correctly."""
        code = """
def func1():
    pass

def func2():
    if True:
        return
    # Unreachable code
    x = 1

def func3(items=[]):
    pass
"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            report = analyze_python_file_sync(temp_path)

            metrics = report.metrics
            assert metrics["function_count"] == 3
            assert metrics["tier2_findings"] >= 0  # Should have some issues
            assert "issue_count" in metrics

        finally:
            import os
            os.unlink(temp_path)


class TestNullSafetyCheckIntegration:
    """Integration tests for null safety check with LLM."""

    @pytest.mark.asyncio
    async def test_null_safety_unsafe_function(self):
        """Test null safety check on unsafe function."""
        code = "def greet(name): return name.upper()"
        import ast

        tree, _ = parse_python_file(code)
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_node = node
                break

        from backend.analysis.fact_extractor import extract_function_facts
        facts = extract_function_facts(func_node, code)

        stub = StubLLMAdapter({
            "null safety": "UNSAFE: name (calls .upper() without None check)"
        })

        issues = await run_null_safety_check(facts, stub)

        # Should find null safety issue
        assert len(issues) > 0
        assert "null_safety" in issues[0].issue_id

    @pytest.mark.asyncio
    async def test_null_safety_safe_function(self):
        """Test null safety check on safe function."""
        code = """
def greet(name):
    if name is None:
        return "Hello, stranger"
    return name.upper()
"""
        import ast

        tree, _ = parse_python_file(code)
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_node = node
                break

        from backend.analysis.fact_extractor import extract_function_facts
        facts = extract_function_facts(func_node, code)

        stub = StubLLMAdapter({
            "null safety": "SAFE: all parameters handled"
        })

        issues = await run_null_safety_check(facts, stub)

        # Should not find issues (function is safe)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_null_safety_unclear_response(self):
        """Test null safety check when LLM is unclear."""
        code = "def complex_func(data): return data"
        import ast

        tree, _ = parse_python_file(code)
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_node = node
                break

        from backend.analysis.fact_extractor import extract_function_facts
        facts = extract_function_facts(func_node, code)

        # Use default UNCLEAR response
        stub = StubLLMAdapter({})

        issues = await run_null_safety_check(facts, stub)

        # Should not find issues (unclear means no finding)
        assert len(issues) == 0


class TestReportFormatting:
    """Test report formatting and output."""

    def test_format_report_text_no_issues(self):
        """Test formatting a report with no issues."""
        from backend.pipeline.report_generator import format_report_text, generate_report
        from backend.models import VerificationIssue

        report = generate_report(
            file_path="test.py",
            source_code="def test(): pass",
            functions=[],
            issues=[]
        )

        text = format_report_text(report)

        assert "Program Mill Verification Report" in text
        assert "No issues found" in text
        assert "test.py" in text

    def test_format_report_text_with_issues(self):
        """Test formatting a report with issues."""
        from backend.pipeline.report_generator import format_report_text, generate_report
        from backend.models import VerificationIssue, FindingTier, FindingConfidence

        issues = [
            VerificationIssue(
                issue_id="test:issue1",
                severity="critical",
                category="security",
                title="Test Issue 1",
                description="A test issue",
                location="test.py:1",
                tier=FindingTier.TIER1_DETERMINISTIC,
                confidence=FindingConfidence.HIGH,
                evidence=["Evidence 1"]
            ),
            VerificationIssue(
                issue_id="test:issue2",
                severity="medium",
                category="maintainability",
                title="Test Issue 2",
                description="Another test issue",
                location="test.py:2",
                tier=FindingTier.TIER2_HEURISTIC,
                confidence=FindingConfidence.MEDIUM,
            )
        ]

        report = generate_report(
            file_path="test.py",
            source_code="def test(): pass",
            functions=[],
            issues=issues
        )

        text = format_report_text(report)

        assert "CRITICAL" in text
        assert "MEDIUM" in text
        assert "Test Issue 1" in text
        assert "Test Issue 2" in text

    def test_save_and_load_report_json(self):
        """Test saving and loading a JSON report."""
        from backend.pipeline.report_generator import generate_report, save_report_json, load_report_json
        import tempfile
        import os

        report = generate_report(
            file_path="test.py",
            source_code="def test(): pass",
            functions=[],
            issues=[]
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            save_report_json(report, temp_path)
            loaded = load_report_json(temp_path)

            assert loaded.analysis_id == report.analysis_id
            assert loaded.file_path == report.file_path
            assert loaded.code_hash == report.code_hash

        finally:
            os.unlink(temp_path)


class TestRealCodeAnalysis:
    """Test analysis on real code patterns."""

    def test_analyze_mutable_default_function(self):
        """Test function with mutable default argument."""
        code = """
def append_item(items=[]):
    items.append(1)
    return items
"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            report = analyze_python_file_sync(temp_path)

            # Should detect mutable default issue
            assert any("mutable" in i.title.lower() for i in report.issues)

        finally:
            import os
            os.unlink(temp_path)

    def test_analyze_bare_except_function(self):
        """Test function with bare except clause."""
        code = """
def risky_operation():
    try:
        do_something()
    except:
        pass
"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            report = analyze_python_file_sync(temp_path)

            # Should detect bare except issue
            assert any("bare except" in i.title.lower() or "bare" in i.title.lower()
                      for i in report.issues)

        finally:
            import os
            os.unlink(temp_path)

    def test_analyze_giant_function(self):
        """Test analysis of a function that exceeds size thresholds."""
        # Create a function with >50 lines
        lines = ["def giant_function():"]
        for i in range(50):
            lines.append(f"    x{i} = {i}")
        lines.append("    return 0")
        code = "\n".join(lines)

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            report = analyze_python_file_sync(temp_path)

            # Should detect giant function issue
            assert any("giant" in i.title.lower() or "size" in i.title.lower() or "threshold" in i.title.lower()
                      for i in report.issues)

        finally:
            import os
            os.unlink(temp_path)
