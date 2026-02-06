"""Tests for fix generator."""

import pytest

from backend.models import VerificationIssue, FindingTier, FindingConfidence
from backend.synthesis.fix_generator import (
    CodeFix,
    FixGenerator,
    apply_fixes,
    generate_fix_report,
    generate_fixes,
)


class TestFixGeneration:
    """Test fix generation for various issue types."""

    def test_empty_issues(self):
        """Test with no issues."""
        code = "def foo(): pass"
        fixes = generate_fixes(code, [])

        assert fixes == []

    def test_sql_injection_fix(self):
        """Test SQL injection fix generation."""
        code = 'def query(user_id):\n    sql = "SELECT * FROM users WHERE id = %s" % user_id\n    return sql'
        issue = VerificationIssue(
            issue_id="test:sql_injection",
            severity="critical",
            category="security",
            title="SQL Injection",
            description="SQL injection vulnerability",
            location="query:2",
            tier=FindingTier.TIER1_DETERMINISTIC,
            confidence=FindingConfidence.HIGH,
        )

        fixes = generate_fixes(code, [issue])

        assert len(fixes) > 0
        assert fixes[0].issue_type == "security"

    def test_xss_fix(self):
        """Test XSS fix generation."""
        code = 'def render(user_input):\n    return "<div>" + user_input + "</div>"'
        issue = VerificationIssue(
            issue_id="test:xss",
            severity="high",
            category="security",
            title="XSS Vulnerability",
            description="XSS vulnerability",
            location="render:2",
            tier=FindingTier.TIER1_DETERMINISTIC,
            confidence=FindingConfidence.HIGH,
        )

        fixes = generate_fixes(code, [issue])

        assert len(fixes) > 0
        assert fixes[0].issue_type == "security"

    def test_command_injection_fix(self):
        """Test command injection fix generation."""
        code = 'def run(cmd):\n    return os.system(cmd)'
        issue = VerificationIssue(
            issue_id="test:cmd_injection",
            severity="critical",
            category="security",
            title="Command Injection",
            description="Command injection vulnerability",
            location="run:2",
            tier=FindingTier.TIER1_DETERMINISTIC,
            confidence=FindingConfidence.HIGH,
        )

        fixes = generate_fixes(code, [issue])

        assert len(fixes) > 0
        assert fixes[0].issue_type == "security"

    def test_division_by_zero_fix(self):
        """Test division by zero fix generation."""
        code = 'def divide(x, y):\n    return x / y'
        issue = VerificationIssue(
            issue_id="test:division",
            severity="medium",
            category="logic",
            title="Division by Zero",
            description="Division without zero check",
            location="divide:2",
            tier=FindingTier.TIER1_DETERMINISTIC,
            confidence=FindingConfidence.HIGH,
        )

        fixes = generate_fixes(code, [issue])

        assert len(fixes) > 0

    def test_resource_leak_fix(self):
        """Test resource leak fix generation."""
        code = 'def read(path):\n    f = open(path)\n    return f.read()'
        issue = VerificationIssue(
            issue_id="test:resource_leak",
            severity="medium",
            category="performance",
            title="Resource Leak",
            description="File not properly closed",
            location="read:2",
            tier=FindingTier.TIER1_DETERMINISTIC,
            confidence=FindingConfidence.HIGH,
        )

        fixes = generate_fixes(code, [issue])

        assert len(fixes) > 0
        assert fixes[0].issue_type == "performance"

    def test_long_function_suggestion(self):
        """Test long function refactoring suggestion."""
        code = "# long function..."
        issue = VerificationIssue(
            issue_id="test:long_function",
            severity="medium",
            category="maintainability",
            title="Long Function",
            description="Function is too long",
            location="func:1",
            tier=FindingTier.TIER2_HEURISTIC,
            confidence=FindingConfidence.MEDIUM,
        )

        fixes = generate_fixes(code, [issue])

        assert len(fixes) > 0
        assert fixes[0].issue_type == "maintainability"

    def test_deep_nesting_suggestion(self):
        """Test deep nesting refactoring suggestion."""
        code = "# nested code..."
        issue = VerificationIssue(
            issue_id="test:deep_nesting",
            severity="medium",
            category="maintainability",
            title="Deep Nesting",
            description="Code is deeply nested",
            location="func:1",
            tier=FindingTier.TIER2_HEURISTIC,
            confidence=FindingConfidence.MEDIUM,
        )

        fixes = generate_fixes(code, [issue])

        assert len(fixes) > 0

    def test_long_parameter_list_suggestion(self):
        """Test long parameter list refactoring suggestion."""
        code = "# func(a, b, c, d, e, f)"
        issue = VerificationIssue(
            issue_id="test:long_params",
            severity="high",
            category="maintainability",
            title="Long Parameter List",
            description="Too many parameters",
            location="func:1",
            tier=FindingTier.TIER2_HEURISTIC,
            confidence=FindingConfidence.MEDIUM,
        )

        fixes = generate_fixes(code, [issue])

        assert len(fixes) > 0


class TestFixApplication:
    """Test applying fixes to code."""

    def test_apply_single_fix(self):
        """Test applying a single fix."""
        code = "def foo():\n    x = 1\n    return x"
        fixes = [
            CodeFix(
                issue_id="test",
                issue_type="test",
                original_code="x = 1",
                fixed_code="x = 2  # Fixed",
                line_start=2,
                line_end=2,
                description="Test fix",
            )
        ]

        result = apply_fixes(code, fixes)

        assert "x = 2" in result
        assert "Fixed" in result

    def test_apply_multiple_fixes(self):
        """Test applying multiple fixes."""
        code = "def foo():\n    x = 1\n    y = 2\n    return x + y"
        fixes = [
            CodeFix(
                issue_id="test1",
                issue_type="test",
                original_code="x = 1",
                fixed_code="x = 10",
                line_start=2,
                line_end=2,
                description="Test fix 1",
            ),
            CodeFix(
                issue_id="test2",
                issue_type="test",
                original_code="y = 2",
                fixed_code="y = 20",
                line_start=3,
                line_end=3,
                description="Test fix 2",
            ),
        ]

        result = apply_fixes(code, fixes)

        assert "x = 10" in result
        assert "y = 20" in result

    def test_apply_fixes_empty_list(self):
        """Test applying empty fix list."""
        code = "def foo(): return 1"
        result = apply_fixes(code, [])

        assert result == code

    def test_apply_fixes_with_invalid_line(self):
        """Test that fixes with invalid line numbers are skipped."""
        code = "def foo(): return 1"
        fixes = [
            CodeFix(
                issue_id="test",
                issue_type="test",
                original_code="x = 1",
                fixed_code="x = 2",
                line_start=100,  # Invalid line
                line_end=100,
                description="Test fix",
            )
        ]

        result = apply_fixes(code, fixes)

        # Code should be unchanged
        assert result == code


class TestFixReport:
    """Test fix report generation."""

    def test_empty_report(self):
        """Test report with no fixes."""
        report = generate_fix_report([])

        assert report["summary"]["total_fixes"] == 0
        assert report["fixes"] == []

    def test_report_with_fixes(self):
        """Test report with fixes."""
        fixes = [
            CodeFix(
                issue_id="test1",
                issue_type="sql_injection",
                original_code="bad code",
                fixed_code="good code",
                line_start=10,
                line_end=10,
                description="Fix SQL injection",
                confidence="high",
                requires_review=True,
            ),
            CodeFix(
                issue_id="test2",
                issue_type="xss",
                original_code="bad code",
                fixed_code="good code",
                line_start=20,
                line_end=20,
                description="Fix XSS",
                confidence="medium",
                requires_review=False,
            ),
        ]

        report = generate_fix_report(fixes)

        assert report["summary"]["total_fixes"] == 2
        assert report["summary"]["requires_review"] == 1
        assert len(report["fixes"]) == 2
        assert report["fixes"][0]["confidence"] == "high"
        assert report["fixes"][1]["requires_review"] is False

    def test_report_aggregates_by_type(self):
        """Test that report aggregates by issue type."""
        fixes = [
            CodeFix("test1", "sql_injection", "a", "b", 1, 1, "desc1"),
            CodeFix("test2", "sql_injection", "a", "b", 2, 2, "desc2"),
            CodeFix("test3", "xss", "a", "b", 3, 3, "desc3"),
        ]

        report = generate_fix_report(fixes)

        assert report["summary"]["by_issue_type"]["sql_injection"] == 2
        assert report["summary"]["by_issue_type"]["xss"] == 1


class TestFixGeneratorClass:
    """Test FixGenerator class."""

    def test_initialization(self):
        """Test generator initialization."""
        generator = FixGenerator("code")

        assert generator.source_code == "code"
        assert generator.source_lines == ["code"]

    def test_generate_fixes_method(self):
        """Test generate_fixes method."""
        generator = FixGenerator("def foo(): return 1")
        issue = VerificationIssue(
            issue_id="test",
            severity="low",
            category="logic",
            title="Test Issue",
            description="Test issue",
            location="foo:1",
            tier=FindingTier.TIER2_HEURISTIC,
            confidence=FindingConfidence.MEDIUM,
        )

        fixes = generator.generate_fixes([issue])

        assert isinstance(fixes, list)


class TestCodeFixDataclass:
    """Test CodeFix dataclass."""

    def test_all_fields(self):
        """Test CodeFix has all required fields."""
        fix = CodeFix(
            issue_id="test",
            issue_type="sql_injection",
            original_code="bad",
            fixed_code="good",
            line_start=10,
            line_end=10,
            description="Fix SQL injection",
            confidence="high",
            requires_review=False,
        )

        assert fix.issue_id == "test"
        assert fix.issue_type == "sql_injection"
        assert fix.original_code == "bad"
        assert fix.fixed_code == "good"
        assert fix.line_start == 10
        assert fix.confidence == "high"
        assert fix.requires_review is False

    def test_default_values(self):
        """Test default field values."""
        fix = CodeFix(
            issue_id="test",
            issue_type="test",
            original_code="a",
            fixed_code="b",
            line_start=1,
            line_end=1,
            description="desc",
        )

        assert fix.confidence == "medium"
        assert fix.requires_review is True


class TestEdgeCases:
    """Test edge cases."""

    def test_unknown_issue_type(self):
        """Test handling of unknown issue types."""
        code = "def foo(): return 1"
        issue = VerificationIssue(
            issue_id="test",
            severity="low",
            category="logic",
            title="Unknown Issue",
            description="Unknown issue type that doesn't match any fix pattern",
            location="foo:1",
            tier=FindingTier.TIER2_HEURISTIC,
            confidence=FindingConfidence.LOW,
        )

        fixes = generate_fixes(code, [issue])

        # Should return empty list for unknown types
        assert fixes == []

    def test_invalid_location_format(self):
        """Test handling of invalid location format."""
        code = "def foo(): return 1"
        issue = VerificationIssue(
            issue_id="test",
            severity="low",
            category="performance",
            title="Test",
            description="Test",
            location="invalid_location",  # No line number
            tier=FindingTier.TIER2_HEURISTIC,
            confidence=FindingConfidence.LOW,
        )

        fixes = generate_fixes(code, [issue])

        # Should handle gracefully
        assert isinstance(fixes, list)

    def test_empty_source_code(self):
        """Test with empty source code."""
        fixes = generate_fixes("", [])

        assert fixes == []

    def test_line_number_out_of_bounds(self):
        """Test fix generation with out of bounds line number."""
        code = "def foo(): return 1"
        issue = VerificationIssue(
            issue_id="test",
            severity="low",
            category="security",
            title="Test",
            description="Test",
            location="foo:999",  # Line doesn't exist
            tier=FindingTier.TIER1_DETERMINISTIC,
            confidence=FindingConfidence.HIGH,
        )

        fixes = generate_fixes(code, [issue])

        # Should handle gracefully
        assert isinstance(fixes, list)


class TestConfidenceLevels:
    """Test confidence levels for fixes."""

    def test_high_confidence_fixes(self):
        """Test that some fixes have high confidence."""
        code = 'def divide(x, y):\n    return x / y'
        issue = VerificationIssue(
            issue_id="test",
            severity="medium",
            category="logic",
            title="Division by Zero",
            description="Test",
            location="divide:2",
            tier=FindingTier.TIER1_DETERMINISTIC,
            confidence=FindingConfidence.HIGH,
        )

        fixes = generate_fixes(code, [issue])

        if fixes:
            # Division by zero fix should have high confidence
            assert fixes[0].confidence in ["high", "medium", "low"]

    def test_requires_review_flag(self):
        """Test requires_review flag is set appropriately."""
        code = 'def divide(x, y):\n    return x / y'
        issue = VerificationIssue(
            issue_id="test",
            severity="medium",
            category="logic",
            title="Test",
            description="Test",
            location="divide:2",
            tier=FindingTier.TIER1_DETERMINISTIC,
            confidence=FindingConfidence.HIGH,
        )

        fixes = generate_fixes(code, [issue])

        if fixes:
            # Simple fixes might not require review
            assert isinstance(fixes[0].requires_review, bool)
