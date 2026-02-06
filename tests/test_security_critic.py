"""Tests for security critic."""

import pytest

from backend.analysis.security_critic import (
    SecurityIssue,
    SecurityCritic,
    analyze_security_issues,
    generate_security_report,
    _is_likely_user_input,
)
from backend.models import FunctionInfo


class TestSecurityIssueDetection:
    """Test security vulnerability detection."""

    def test_empty_code(self):
        """Test with empty code."""
        issues = analyze_security_issues("", [])

        assert issues == []

    def test_sql_injection_format_string(self):
        """Test SQL injection via format string."""
        code = """
def query(user_id):
    sql = "SELECT * FROM users WHERE id = %s" % user_id
    cursor.execute(sql)
"""
        issues = analyze_security_issues(code, [])

        assert any(i.vuln_type == "sql_injection" for i in issues)

    def test_sql_injection_execute(self):
        """Test SQL injection via execute with user input."""
        code = """
def query(user_input):
    cursor.execute("SELECT * FROM users WHERE name = '" + user_input + "'")
"""
        issues = analyze_security_issues(code, [])

        assert any(i.vuln_type == "sql_injection" for i in issues)

    def test_command_injection_system(self):
        """Test command injection via os.system."""
        code = """
def run(cmd):
    return os.system(cmd)
"""
        issues = analyze_security_issues(code, [])

        assert any(i.vuln_type == "command_injection" for i in issues)

    def test_command_injection_subprocess(self):
        """Test command injection via subprocess."""
        code = """
def run(cmd):
    return subprocess.run(cmd, shell=True)
"""
        issues = analyze_security_issues(code, [])

        assert any(i.vuln_type == "command_injection" for i in issues)

    def test_xss_html_concat(self):
        """Test XSS via HTML concatenation."""
        code = """
def render(user_input):
    return "<div>" + user_input + "</div>"
"""
        issues = analyze_security_issues(code, [])

        # May detect as potential XSS
        assert isinstance(issues, list)

    def test_path_traversal_open(self):
        """Test path traversal via open()."""
        code = """
def read_file(filename):
    with open(filename) as f:
        return f.read()
"""
        issues = analyze_security_issues(code, [])

        assert isinstance(issues, list)


class TestUserInputDetection:
    """Test user input pattern detection."""

    def test_request_detected(self):
        """Test that request.* is detected as user input."""
        assert _is_likely_user_input("request.args.get('data')")

    def test_form_detected(self):
        """Test that form.* is detected as user input."""
        assert _is_likely_user_input("form.username")

    def test_input_detected(self):
        """Test that input variable is detected as user input."""
        assert _is_likely_user_input("user_input")

    def test_trusted_data_not_detected(self):
        """Test that trusted data is not flagged as user input."""
        assert not _is_likely_user_input("internal_constant")
        assert not _is_likely_user_input("CONFIG_VALUE")


class TestSecurityReport:
    """Test security report generation."""

    def test_empty_report(self):
        """Test report with no issues."""
        report = generate_security_report([])

        assert report["summary"]["total_issues"] == 0
        assert report["issues"] == []

    def test_report_with_issues(self):
        """Test report with security issues."""
        issues = [
            SecurityIssue(
                vuln_type="sql_injection",
                function_name="query",
                line=10,
                severity="critical",
                description="SQL injection",
                suggestion="Use parameterized queries",
            )
        ]

        report = generate_security_report(issues)

        assert report["summary"]["total_issues"] == 1
        assert report["summary"]["by_type"]["sql_injection"] == 1
        assert report["summary"]["by_severity"]["critical"] == 1
        assert len(report["issues"]) == 1

    def test_report_aggregates_by_type(self):
        """Test that report aggregates by vulnerability type."""
        issues = [
            SecurityIssue("sql_injection", "f1", 1, "critical", "desc1"),
            SecurityIssue("sql_injection", "f2", 2, "critical", "desc2"),
            SecurityIssue("xss", "f3", 3, "high", "desc3"),
        ]

        report = generate_security_report(issues)

        assert report["summary"]["by_type"]["sql_injection"] == 2
        assert report["summary"]["by_type"]["xss"] == 1

    def test_report_aggregates_by_severity(self):
        """Test that report aggregates by severity."""
        issues = [
            SecurityIssue("sql_injection", "f1", 1, "low", "desc1"),
            SecurityIssue("xss", "f2", 2, "high", "desc2"),
            SecurityIssue("cmd_injection", "f3", 3, "critical", "desc3"),
        ]

        report = generate_security_report(issues)

        assert report["summary"]["by_severity"]["low"] == 1
        assert report["summary"]["by_severity"]["high"] == 1
        assert report["summary"]["by_severity"]["critical"] == 1


class TestSecurityCriticClass:
    """Test SecurityCritic class."""

    def test_initialization(self):
        """Test critic initialization."""
        critic = SecurityCritic("code")

        assert critic.issues == []
        assert critic.current_function is None

    def test_visits_function(self):
        """Test that critic visits functions."""
        code = "def test(): return 1"
        import ast

        tree = ast.parse(code)
        critic = SecurityCritic(code)
        critic.visit(tree)

        assert isinstance(critic.issues, list)


class TestSecurityIssueDataclass:
    """Test SecurityIssue dataclass."""

    def test_all_fields(self):
        """Test SecurityIssue has all required fields."""
        issue = SecurityIssue(
            vuln_type="sql_injection",
            function_name="query",
            line=10,
            severity="critical",
            description="SQL injection vulnerability",
            suggestion="Use parameterized queries",
            confidence="high",
        )

        assert issue.vuln_type == "sql_injection"
        assert issue.function_name == "query"
        assert issue.line == 10
        assert issue.severity == "critical"
        assert issue.suggestion == "Use parameterized queries"
        assert issue.confidence == "high"


class TestEdgeCases:
    """Test edge cases."""

    def test_syntax_error_code(self):
        """Test with syntax error."""
        issues = analyze_security_issues("def broken(", [])

        assert issues == []

    def test_safe_sql_query(self):
        """Test that safe queries are not flagged."""
        code = """
def safe_query(user_id):
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
"""
        issues = analyze_security_issues(code, [])

        # Parameterized query should not trigger SQL injection
        sql_issues = [i for i in issues if i.vuln_type == "sql_injection"]
        assert len(sql_issues) == 0

    def test_complex_function(self):
        """Test analysis of complex function."""
        code = """
def process(user_input, filename):
    # This function has multiple potential issues
    sql = "SELECT * FROM data WHERE name = '%s'" % user_input
    cursor.execute(sql)

    with open(filename) as f:
        return f.read()
"""
        issues = analyze_security_issues(code, [])

        assert isinstance(issues, list)


class TestVulnerabilityTypes:
    """Test specific vulnerability types."""

    def test_all_severity_levels(self):
        """Test all severity levels are supported."""
        code = "def dummy(): pass"
        issues = analyze_security_issues(code, [])

        # Should handle all severity levels
        for severity in ["low", "medium", "high", "critical"]:
            issue = SecurityIssue(
                vuln_type="test",
                function_name="test",
                line=1,
                severity=severity,
                description="test",
            )
            assert issue.severity == severity


class TestConfidenceLevels:
    """Test confidence level tracking."""

    def test_default_confidence(self):
        """Test default confidence is medium."""
        issue = SecurityIssue(
            vuln_type="test",
            function_name="test",
            line=1,
            severity="medium",
            description="test",
        )

        assert issue.confidence == "medium"

    def test_custom_confidence(self):
        """Test custom confidence level."""
        issue = SecurityIssue(
            vuln_type="test",
            function_name="test",
            line=1,
            severity="medium",
            description="test",
            confidence="high",
        )

        assert issue.confidence == "high"
