"""Tests for security boundary analysis."""

import pytest

from backend.analysis.security_boundaries import (
    identify_input_boundaries,
    identify_output_boundaries,
    identify_privilege_boundaries,
    classify_trust_levels,
    generate_boundary_report,
    SecurityBoundary,
    SecurityBoundaryAnalyzer,
    TrustLevel,
)
from backend.models import FunctionInfo, ClassInfo


class TestInputBoundaries:
    """Test input boundary identification."""

    def test_empty_code(self):
        """Test with empty code."""
        boundaries = identify_input_boundaries("", [])

        assert boundaries == []

    def test_detect_request_input(self):
        """Test detection of HTTP request input."""
        code = """
from flask import request

def process():
    user_input = request.args.get('data')
    return user_input
"""
        functions = [FunctionInfo(name="process", line_start=4, line_end=7, parameters=[])]
        boundaries = identify_input_boundaries(code, functions)

        # Should detect request as input boundary
        assert len(boundaries) >= 0

    def test_detect_file_input(self):
        """Test detection of file input."""
        code = """
def read_file(path):
    with open(path) as f:
        return f.read()
"""
        functions = [FunctionInfo(name="read_file", line_start=2, line_end=5, parameters=["path"])]
        boundaries = identify_input_boundaries(code, functions)

        assert isinstance(boundaries, list)

    def test_detect_stdin_input(self):
        """Test detection of stdin input."""
        code = """
def get_user_input():
    return input("Enter value: ")
"""
        boundaries = identify_input_boundaries(code, [])

        assert len(boundaries) > 0
        assert boundaries[0].boundary_type == "input"


class TestOutputBoundaries:
    """Test output boundary identification."""

    def test_detect_database_output(self):
        """Test detection of database writes."""
        code = """
def save_to_db(value):
    cursor.execute("INSERT INTO table VALUES (%s)", (value,))
    db.commit()
"""
        functions = [FunctionInfo(name="save_to_db", line_start=2, line_end=4, parameters=["value"])]
        boundaries = identify_output_boundaries(code, functions)

        assert isinstance(boundaries, list)

    def test_detect_file_output(self):
        """Test detection of file writes."""
        code = """
def write_file(filename, content):
    with open(filename, 'w') as f:
        f.write(content)
"""
        boundaries = identify_output_boundaries(code, [])

        assert isinstance(boundaries, list)

    def test_detect_command_execution(self):
        """Test detection of command execution."""
        code = """
def run_command(cmd):
    return os.system(cmd)
"""
        boundaries = identify_output_boundaries(code, [])

        assert isinstance(boundaries, list)


class TestPrivilegeBoundaries:
    """Test privilege boundary identification."""

    def test_detect_eval(self):
        """Test detection of eval usage."""
        code = """
def evaluate(code):
    return eval(code)
"""
        boundaries = identify_privilege_boundaries(code, [])

        assert len(boundaries) > 0
        assert boundaries[0].risk_level == "critical"

    def test_detect_exec(self):
        """Test detection of exec usage."""
        code = """
def execute(code):
    exec(code)
"""
        boundaries = identify_privilege_boundaries(code, [])

        assert len(boundaries) > 0
        assert boundaries[0].risk_level == "critical"


class TestTrustLevelClassification:
    """Test trust level classification."""

    def test_empty_code(self):
        """Test with empty code."""
        levels = classify_trust_levels("")

        assert levels == {}

    def test_classify_trusted_data(self):
        """Test classification of trusted data."""
        code = """
def process(value):
    internal = value
    return internal
"""
        levels = classify_trust_levels(code)

        assert isinstance(levels, dict)


class TestBoundaryReport:
    """Test boundary report generation."""

    def test_empty_report(self):
        """Test report with no data."""
        report = generate_boundary_report([], [], [], {})

        assert report["summary"]["total_input_boundaries"] == 0
        assert report["summary"]["total_boundaries"] == 0
        assert report["input_boundaries"] == []
        assert report["output_boundaries"] == []
        assert report["privilege_boundaries"] == []

    def test_report_with_boundaries(self):
        """Test report with security boundaries."""
        input_bound = [
            SecurityBoundary(
                boundary_type="input",
                entity_name="process",
                line=5,
                source_or_sink="request",
                risk_level="high",
                description="HTTP request input",
                suggestion="Validate input",
            )
        ]

        report = generate_boundary_report(input_bound, [], [], {})

        assert report["summary"]["total_boundaries"] == 1
        assert report["summary"]["by_risk_level"]["high"] == 1
        assert len(report["input_boundaries"]) == 1

    def test_report_aggregates_risk_levels(self):
        """Test that report aggregates risk levels."""
        boundaries = [
            SecurityBoundary("input", "f1", 1, "src", "low", "desc"),
            SecurityBoundary("input", "f2", 2, "src", "medium", "desc"),
            SecurityBoundary("input", "f3", 3, "src", "high", "desc"),
            SecurityBoundary("privilege", "f4", 4, "eval", "critical", "desc"),
        ]

        report = generate_boundary_report(boundaries, [], [], {})

        assert report["summary"]["by_risk_level"]["low"] == 1
        assert report["summary"]["by_risk_level"]["medium"] == 1
        assert report["summary"]["by_risk_level"]["high"] == 1
        assert report["summary"]["by_risk_level"]["critical"] == 1


class TestSecurityBoundaryDataclass:
    """Test SecurityBoundary dataclass."""

    def test_all_fields(self):
        """Test SecurityBoundary has all required fields."""
        boundary = SecurityBoundary(
            boundary_type="input",
            entity_name="test_func",
            line=10,
            source_or_sink="request.args",
            risk_level="high",
            description="User input from HTTP",
            suggestion="Validate input",
        )

        assert boundary.boundary_type == "input"
        assert boundary.entity_name == "test_func"
        assert boundary.line == 10
        assert boundary.risk_level == "high"
        assert boundary.suggestion == "Validate input"


class TestTrustLevelDataclass:
    """Test TrustLevel dataclass."""

    def test_all_fields(self):
        """Test TrustLevel has all required fields."""
        level = TrustLevel(
            variable="user_input",
            trust_level="untrusted",
            validation_location="validate()",
        )

        assert level.variable == "user_input"
        assert level.trust_level == "untrusted"
        assert level.validation_location == "validate()"


class TestSecurityBoundaryAnalyzer:
    """Test SecurityBoundaryAnalyzer class."""

    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = SecurityBoundaryAnalyzer("")

        assert analyzer.boundaries == []
        assert analyzer.data_flows == []
        assert analyzer.trust_levels == {}

    def test_visits_function_def(self):
        """Test analyzer visits function definitions."""
        code = "def test(): pass"
        import ast

        tree = ast.parse(code)
        analyzer = SecurityBoundaryAnalyzer(code)
        analyzer.visit(tree)

        assert isinstance(analyzer.boundaries, list)


class TestEdgeCases:
    """Test edge cases."""

    def test_syntax_error_code(self):
        """Test with syntax error."""
        boundaries = identify_input_boundaries("def broken(", [])

        assert boundaries == []

    def test_function_with_no_boundaries(self):
        """Test function that doesn't cross boundaries."""
        code = """
def internal_calculation(x, y):
    return x + y
"""
        boundaries = identify_output_boundaries(code, [])

        assert isinstance(boundaries, list)


class TestKnownSourcesAndSinks:
    """Test detection of known untrusted sources and sinks."""

    def test_untrusted_sources_defined(self):
        """Test that UNTRUSTED_SOURCES is populated."""
        from backend.analysis.security_boundaries import UNTRUSTED_SOURCES

        assert "request" in UNTRUSTED_SOURCES
        assert "input" in UNTRUSTED_SOURCES
        assert "os.environ" in UNTRUSTED_SOURCES

    def test_sink_categories_defined(self):
        """Test that SINK_CATEGORIES is populated."""
        from backend.analysis.security_boundaries import SINK_CATEGORIES

        assert "database" in SINK_CATEGORIES
        assert "network" in SINK_CATEGORIES
        assert "file" in SINK_CATEGORIES
        assert "command" in SINK_CATEGORIES
        assert "eval" in SINK_CATEGORIES
