"""Fix generation for detected issues.

This module generates:
- Suggested fixes for security vulnerabilities
- Code improvements for performance issues
- Refactoring suggestions for maintainability
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional

import structlog

from backend.models import FunctionInfo, VerificationIssue

logger = structlog.get_logger()


@dataclass
class CodeFix:
    """A suggested fix for an issue."""

    issue_id: str
    issue_type: str
    original_code: str
    fixed_code: str
    line_start: int
    line_end: int
    description: str
    confidence: str = "medium"
    requires_review: bool = True


class FixGenerator:
    """Generate fixes for detected issues."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.source_lines = source_code.splitlines()

    def generate_fixes(self, issues: List[VerificationIssue]) -> List[CodeFix]:
        """
        Generate fixes for a list of issues.

        Args:
            issues: List of verification issues

        Returns:
            List of CodeFix objects
        """
        fixes: List[CodeFix] = []

        for issue in issues:
            fix = self._generate_fix_for_issue(issue)
            if fix:
                fixes.append(fix)

        return fixes

    def _generate_fix_for_issue(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Generate a fix for a single issue."""
        # Use issue title and description to determine fix type
        title = issue.title.lower()
        description = issue.description.lower()

        if "sql" in title or "sql" in description or "injection" in title:
            return self._fix_sql_injection(issue)
        elif "xss" in title or "xss" in description or "html" in title:
            return self._fix_xss(issue)
        elif "command" in title or "command" in description or "os.system" in description:
            return self._fix_command_injection(issue)
        elif "path" in title or "traversal" in title or "file" in description:
            return self._fix_path_traversal(issue)
        elif "division" in title or "division" in description or "zero" in title:
            return self._fix_division_by_zero(issue)
        elif "none" in title or "optional" in description or "dereference" in title:
            return self._fix_none_check(issue)
        elif "long function" in title or "long" in description:
            return self._suggest_extraction(issue)
        elif "nesting" in title or "nested" in description:
            return self._suggest_guard_clauses(issue)
        elif "parameter" in title or "parameter" in description:
            return self._suggest_parameter_grouping(issue)
        elif "resource" in title or "leak" in title or "file not closed" in description:
            return self._fix_resource_leak(issue)

        return None

    def _fix_sql_injection(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Generate fix for SQL injection."""
        # Extract the problematic line
        line_num = self._parse_line_from_location(issue.location)
        if line_num is None or line_num > len(self.source_lines):
            return None

        original_line = self.source_lines[line_num - 1]

        # Generate suggested fix
        # This is a simplified fix - real implementation would parse the SQL
        fixed_line = original_line.replace(' f"', '", params)  # Use parameterized query')
        fixed_line = fixed_line.replace('" % ', '", % (params))  # Use parameterized query')

        if fixed_line == original_line:
            # Try string concatenation pattern
            if " + " in original_line and "SELECT" in original_line.upper():
                fixed_line = "# TODO: Rewrite using parameterized query"

        return CodeFix(
            issue_id=issue.issue_id,
            issue_type=issue.category,
            original_code=original_line,
            fixed_code=fixed_line,
            line_start=line_num,
            line_end=line_num,
            description="Use parameterized queries to prevent SQL injection",
            confidence="medium",
            requires_review=True,
        )

    def _fix_xss(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Generate fix for XSS vulnerability."""
        line_num = self._parse_line_from_location(issue.location)
        if line_num is None or line_num > len(self.source_lines):
            return None

        original_line = self.source_lines[line_num - 1]

        # Suggest using html.escape
        fixed_line = original_line.replace(
            ' + ',
            ' + html.escape('
        )

        return CodeFix(
            issue_id=issue.issue_id,
            issue_type=issue.category,
            original_code=original_line,
            fixed_code=fixed_line + "  # Add: import html; html.escape(user_input)",
            line_start=line_num,
            line_end=line_num,
            description="Escape HTML output to prevent XSS",
            confidence="medium",
            requires_review=True,
        )

    def _fix_command_injection(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Generate fix for command injection."""
        line_num = self._parse_line_from_location(issue.location)
        if line_num is None or line_num > len(self.source_lines):
            return None

        original_line = self.source_lines[line_num - 1]

        fixed_code = """# Use subprocess.run with list argument instead
subprocess.run([\"command\", \"arg1\", \"arg2\"], check=True)"""

        return CodeFix(
            issue_id=issue.issue_id,
            issue_type=issue.category,
            original_code=original_line,
            fixed_code=fixed_code,
            line_start=line_num,
            line_end=line_num,
            description="Use subprocess.run with list of arguments to prevent command injection",
            confidence="high",
            requires_review=True,
        )

    def _fix_path_traversal(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Generate fix for path traversal."""
        line_num = self._parse_line_from_location(issue.location)
        if line_num is None or line_num > len(self.source_lines):
            return None

        original_line = self.source_lines[line_num - 1]

        fixed_code = """# Validate and sanitize file path
safe_path = os.path.normpath(user_path)
if not safe_path.startswith(allowed_base_dir):
    raise ValueError(\"Path traversal attempt detected\")
with open(safe_path) as f:
    ..."""

        return CodeFix(
            issue_id=issue.issue_id,
            issue_type=issue.category,
            original_code=original_line,
            fixed_code=fixed_code,
            line_start=line_num,
            line_end=line_num,
            description="Validate file paths to prevent path traversal attacks",
            confidence="high",
            requires_review=True,
        )

    def _fix_division_by_zero(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Generate fix for division by zero."""
        line_num = self._parse_line_from_location(issue.location)
        if line_num is None or line_num > len(self.source_lines):
            return None

        original_line = self.source_lines[line_num - 1]

        fixed_code = "# Add: if denominator != 0 before division\n" + original_line

        return CodeFix(
            issue_id=issue.issue_id,
            issue_type=issue.category,
            original_code=original_line,
            fixed_code=fixed_code,
            line_start=line_num,
            line_end=line_num,
            description="Check denominator is not zero before division",
            confidence="high",
            requires_review=False,
        )

    def _fix_none_check(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Generate fix for missing None check."""
        line_num = self._parse_line_from_location(issue.location)
        if line_num is None or line_num > len(self.source_lines):
            return None

        original_line = self.source_lines[line_num - 1]

        fixed_code = f"""# Add guard clause
if value is None:
    return None  # or handle appropriately
{original_line}"""

        return CodeFix(
            issue_id=issue.issue_id,
            issue_type=issue.category,
            original_code=original_line,
            fixed_code=fixed_code,
            line_start=line_num,
            line_end=line_num,
            description="Add None check before using optional value",
            confidence="high",
            requires_review=False,
        )

    def _suggest_extraction(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Suggest function extraction for long functions."""
        return CodeFix(
            issue_id=issue.issue_id,
            issue_type=issue.category,
            original_code="# Long function body...",
            fixed_code="""# Extract logical blocks into helper functions
def helper_function1():
    # Sub-task 1
    pass

def helper_function2():
    # Sub-task 2
    pass

def main_function():
    helper_function1()
    helper_function2()""",
            line_start=0,
            line_end=0,
            description="Extract smaller functions to improve readability",
            confidence="low",
            requires_review=True,
        )

    def _suggest_guard_clauses(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Suggest guard clauses to reduce nesting."""
        return CodeFix(
            issue_id=issue.issue_id,
            issue_type=issue.category,
            original_code="# Nested code...",
            fixed_code="""# Use guard clauses (early returns) to reduce nesting
def function(value):
    if not value:
        return None  # Early exit

    # Main logic here, at reduced nesting level
    return process(value)""",
            line_start=0,
            line_end=0,
            description="Use guard clauses to reduce nesting depth",
            confidence="medium",
            requires_review=True,
        )

    def _suggest_parameter_grouping(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Suggest grouping related parameters."""
        return CodeFix(
            issue_id=issue.issue_id,
            issue_type=issue.category,
            original_code="# func(a, b, c, d, e, f)",
            fixed_code="""from dataclasses import dataclass

@dataclass
class Config:
    a: int
    b: str
    c: bool
    # ... related parameters

def func(config: Config):
    # Use config.a, config.b, etc.
    pass""",
            line_start=0,
            line_end=0,
            description="Group related parameters into a dataclass or config object",
            confidence="medium",
            requires_review=True,
        )

    def _fix_resource_leak(self, issue: VerificationIssue) -> Optional[CodeFix]:
        """Generate fix for resource leak."""
        line_num = self._parse_line_from_location(issue.location)
        if line_num is None or line_num > len(self.source_lines):
            return None

        original_line = self.source_lines[line_num - 1]

        fixed_code = original_line.replace(
            "open(",
            "with open("
        ).replace(
            "= open(",
            "= open("
        )

        # Ensure proper with statement syntax
        if "with open(" in fixed_code and " as " not in fixed_code:
            fixed_code = fixed_code.replace(") ", ") as f: ")

        return CodeFix(
            issue_id=issue.issue_id,
            issue_type=issue.category,
            original_code=original_line,
            fixed_code=fixed_code,
            line_start=line_num,
            line_end=line_num,
            description="Use context manager (with statement) for automatic resource cleanup",
            confidence="high",
            requires_review=False,
        )

    def _parse_line_from_location(self, location: str) -> Optional[int]:
        """Extract line number from location string."""
        try:
            # Format is usually "function_name:line_number"
            if ":" in location:
                return int(location.split(":")[-1])
            return None
        except (ValueError, IndexError):
            return None


def generate_fixes(
    source_code: str,
    issues: List[VerificationIssue],
) -> List[CodeFix]:
    """
    Generate fixes for detected issues.

    Args:
        source_code: Python source code
        issues: List of verification issues

    Returns:
        List of CodeFix objects
    """
    generator = FixGenerator(source_code)
    return generator.generate_fixes(issues)


def apply_fixes(
    source_code: str,
    fixes: List[CodeFix],
) -> str:
    """
    Apply fixes to source code.

    Args:
        source_code: Original source code
        fixes: List of fixes to apply

    Returns:
        Modified source code with fixes applied
    """
    lines = source_code.splitlines()

    # Sort fixes by line number in reverse order to avoid offset issues
    sorted_fixes = sorted(
        [f for f in fixes if f.line_start > 0],
        key=lambda f: f.line_start,
        reverse=True
    )

    for fix in sorted_fixes:
        if fix.line_start <= len(lines):
            # Replace the line
            lines[fix.line_start - 1] = fix.fixed_code

    return "\n".join(lines)


def generate_fix_report(fixes: List[CodeFix]) -> dict:
    """
    Generate fix report.

    Args:
        fixes: List of code fixes

    Returns:
        Dict with summary and details
    """
    return {
        "summary": {
            "total_fixes": len(fixes),
            "requires_review": sum(1 for f in fixes if f.requires_review),
            "by_issue_type": {
                fix.issue_type: len([f for f in fixes if f.issue_type == fix.issue_type])
                for fix in fixes
            },
        },
        "fixes": [
            {
                "issue_id": fix.issue_id,
                "issue_type": fix.issue_type,
                "line": fix.line_start,
                "description": fix.description,
                "original": fix.original_code[:100],  # Truncate for report
                "fixed": fix.fixed_code[:100],
                "confidence": fix.confidence,
                "requires_review": fix.requires_review,
            }
            for fix in fixes
        ],
    }
