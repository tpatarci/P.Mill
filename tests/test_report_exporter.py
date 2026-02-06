"""Tests for report exporter."""

import json
import pytest

from backend.analysis.unified_analyzer import analyze_code
from backend.parsing.report_exporter import (
    ReportExporter,
    export_report,
    format_console_report,
)


class TestReportExporter:
    """Test report exporter."""

    def test_to_json(self):
        """Test JSON export."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        exporter = ReportExporter(result)
        json_str = exporter.to_json()

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["analysis_id"] == result.analysis_id
        assert data["file_path"] == "unknown.py"

    def test_to_sarif(self):
        """Test SARIF export."""
        code = """
def divide(x, y):
    return x / y
"""
        result = analyze_code(code)

        exporter = ReportExporter(result)
        sarif = exporter.to_sarif()

        assert isinstance(sarif, dict)
        assert sarif["version"] == "2.1.0"
        assert "runs" in sarif
        assert len(sarif["runs"]) == 1

    def test_to_console(self):
        """Test console report formatting."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        exporter = ReportExporter(result)
        console = exporter.to_console()

        assert isinstance(console, str)
        assert "P.Mill Analysis Report" in console
        assert result.file_path in console

    def test_to_html(self):
        """Test HTML report generation."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        exporter = ReportExporter(result)
        html = exporter.to_html()

        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "P.Mill Analysis Report" in html
        assert result.file_path in html


class TestExportReport:
    """Test export_report function."""

    def test_export_json(self):
        """Test JSON export via export_report."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        json_str = export_report(result, format="json")

        data = json.loads(json_str)
        assert data["analysis_id"] == result.analysis_id

    def test_export_console(self):
        """Test console format export."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        console = export_report(result, format="console")

        assert "P.Mill Analysis Report" in console

    def test_export_html(self):
        """Test HTML export."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        html = export_report(result, format="html")

        assert "<!DOCTYPE html>" in html
        assert "P.Mill Analysis Report" in html

    def test_export_sarif(self):
        """Test SARIF export."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        sarif = export_report(result, format="sarif")

        data = json.loads(sarif)
        assert data["version"] == "2.1.0"

    def test_unknown_format_raises_error(self):
        """Test that unknown format raises ValueError."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        with pytest.raises(ValueError, match="Unknown format"):
            export_report(result, format="unknown")


class TestFormatConsoleReport:
    """Test format_console_report convenience function."""

    def test_format_console_report(self):
        """Test console report formatting."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        console = format_console_report(result)

        assert isinstance(console, str)
        assert "P.Mill Analysis Report" in console


class TestReportWithIssues:
    """Test reports with actual issues."""

    def test_console_shows_issues(self):
        """Test that console report shows issues."""
        code = """
def divide(x, y):
    return x / y

def insecure():
    sql = "SELECT * FROM users WHERE id = %s" % user_input
    return sql
"""
        result = analyze_code(code)

        console = ReportExporter(result).to_console()

        # Should show issues
        assert "SUMMARY" in console

    def test_json_includes_issues(self):
        """Test that JSON includes issues."""
        code = """
def divide(x, y):
    return x / y
"""
        result = analyze_code(code)

        json_str = ReportExporter(result).to_json()
        data = json.loads(json_str)

        assert "issues" in data
        assert "logic" in data["issues"]

    def test_sarif_includes_results(self):
        """Test that SARIF includes results."""
        code = """
def divide(x, y):
    return x / y
"""
        result = analyze_code(code)

        sarif = ReportExporter(result).to_sarif()

        assert "results" in sarif["runs"][0]


class TestSeverityMapping:
    """Test severity to SARIF level mapping."""

    def test_critical_to_error(self):
        """Test critical severity maps to error level."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        exporter = ReportExporter(result)
        assert exporter._map_severity_to_level("critical") == "error"

    def test_high_to_error(self):
        """Test high severity maps to error level."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        exporter = ReportExporter(result)
        assert exporter._map_severity_to_level("high") == "error"

    def test_medium_to_warning(self):
        """Test medium severity maps to warning level."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        exporter = ReportExporter(result)
        assert exporter._map_severity_to_level("medium") == "warning"

    def test_low_to_note(self):
        """Test low severity maps to note level."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        exporter = ReportExporter(result)
        assert exporter._map_severity_to_level("low") == "note"


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_analysis(self):
        """Test with minimal code."""
        code = ""
        result = analyze_code(code)

        exporter = ReportExporter(result)
        assert exporter.to_json()

    def test_analysis_with_error(self):
        """Test export handles analysis errors gracefully."""
        code = "def broken("
        result = analyze_code(code)

        exporter = ReportExporter(result)
        console = exporter.to_console()

        # Should show error
        assert "Error" in console or console.count("Error") >= 1
