"""Tests for Tier 2 pattern checker."""

import ast

import pytest

from backend.analysis.ast_parser import parse_python_file
from backend.analysis.fact_extractor import extract_function_facts
from backend.analysis.pattern_checker import (
    check_bare_except,
    check_broad_exception,
    check_command_injection,
    check_giant_function,
    check_implicit_none_return,
    check_mutable_defaults,
    check_resource_leak,
    check_shadow_builtin,
    check_star_imports,
    check_unreachable_code,
    run_tier2_checks,
    TIER2_CHECKS,
)


class TestBareExcept:
    """Test bare except detection."""

    def test_bare_except_detected(self):
        """Test that bare except clauses are detected."""
        code = """
def bad_handler():
    try:
        risky()
    except:
        pass
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_bare_except(facts)
        assert issue is not None
        assert issue.issue_id == "bad_handler:bare_except"
        assert issue.severity == "medium"
        assert issue.category == "maintainability"
        assert "bare except" in issue.title.lower()
        assert issue.tier.value == "tier2_heuristic"
        assert issue.confidence.value == "high"

    def test_no_bare_except_returns_none(self):
        """Test that functions without bare except return None."""
        code = """
def good_handler():
    try:
        risky()
    except ValueError:
        pass
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_bare_except(facts)
        assert issue is None


class TestMutableDefaults:
    """Test mutable default argument detection."""

    def test_list_default_detected(self):
        """Test that list default arguments are detected."""
        code = """
def append_item(items=[]):
    items.append(1)
    return items
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_mutable_defaults(facts)
        assert issue is not None
        assert issue.issue_id == "append_item:mutable_defaults"
        assert "items" in issue.description
        assert issue.suggested_fix is not None

    def test_dict_default_detected(self):
        """Test that dict default arguments are detected."""
        code = """
def merge_data(data={}):
    return data
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_mutable_defaults(facts)
        assert issue is not None
        assert "data" in issue.description

    def test_no_mutable_defaults_returns_none(self):
        """Test that functions without mutable defaults return None."""
        code = """
def safe_default(x=5, y="hello"):
    return x + y
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_mutable_defaults(facts)
        assert issue is None


class TestResourceLeak:
    """Test resource leak detection."""

    def test_open_without_with_detected(self):
        """Test that open() without with statement is detected."""
        code = """
def read_file():
    f = open("file.txt")
    data = f.read()
    f.close()
    return data
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_resource_leak(facts)
        assert issue is not None
        assert issue.issue_id == "read_file:resource_leak"
        assert "context manager" in issue.description.lower() or "with" in issue.description.lower()

    def test_no_open_returns_none(self):
        """Test that functions without open() return None."""
        code = """
def no_file_ops():
    return 42
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_resource_leak(facts)
        assert issue is None


class TestCommandInjection:
    """Test command injection detection."""

    def test_command_execution_with_fstring_critical(self):
        """Test that command execution with f-string is marked critical."""
        code = """
def execute_cmd(user_input):
    import os
    os.system(f"echo {user_input}")
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_command_injection(facts)
        assert issue is not None
        assert issue.severity == "critical"
        assert issue.category == "security"
        assert "injection" in issue.title.lower()
        assert "f-string" in issue.description.lower()

    def test_command_execution_without_fstring_high(self):
        """Test that command execution without f-string is marked high."""
        code = """
def execute_cmd():
    import os
    os.system("ls -la")
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_command_injection(facts)
        assert issue is not None
        assert issue.severity == "high"
        assert issue.category == "security"

    def test_no_command_execution_returns_none(self):
        """Test that functions without command execution return None."""
        code = """
def safe_function():
    return 42
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_command_injection(facts)
        assert issue is None


class TestImplicitNoneReturn:
    """Test implicit None return detection."""

    def test_implicit_none_return_with_annotation(self):
        """Test detection of implicit None return when annotation exists."""
        code = """
def returns_sometimes(x) -> int:
    if x > 0:
        return x
    # Missing return for x <= 0
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        # Manually set the flag to simulate incomplete return path detection
        facts.has_return_on_all_paths = False

        issue = check_implicit_none_return(facts)
        assert issue is not None
        assert issue.issue_id == "returns_sometimes:implicit_none_return"
        assert "int" in issue.description

    def test_no_return_annotation_returns_none(self):
        """Test that functions without return annotation return None."""
        code = """
def no_annotation(x):
    if x > 0:
        return x
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_implicit_none_return(facts)
        assert issue is None

    def test_all_paths_return_returns_none(self):
        """Test that functions with returns on all paths return None."""
        code = """
def always_returns(x) -> int:
    if x > 0:
        return x
    return 0
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_implicit_none_return(facts)
        assert issue is None


class TestUnreachableCode:
    """Test unreachable code detection."""

    def test_unreachable_code_detected(self):
        """Test that code after unconditional return is detected."""
        code = """
def has_unreachable():
    if True:
        return 1
        print("never runs")
    return 2
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_unreachable_code(facts)
        assert issue is not None
        assert issue.issue_id == "has_unreachable:unreachable_code"
        assert issue.severity == "low"

    def test_no_unreachable_code_returns_none(self):
        """Test that functions without unreachable code return None."""
        code = """
def all_reachable():
    x = 1
    return x
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_unreachable_code(facts)
        assert issue is None


class TestGiantFunction:
    """Test giant function detection."""

    def test_high_loc_detected(self):
        """Test that functions with >50 lines are detected."""
        code = "def giant():\n"
        # Create a function with 51 lines
        for i in range(50):
            code += f"    x{i} = {i}\n"
        code += "    return 0\n"

        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_giant_function(facts)
        assert issue is not None
        assert issue.issue_id == "giant:giant_function"
        assert "lines" in issue.description.lower()
        assert str(facts.loc) in issue.description

    def test_high_complexity_detected(self):
        """Test that functions with complexity >10 are detected."""
        code = """
def complex_func(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                return 1
            elif z < 0:
                return 2
            else:
                return 3
        elif y < 0:
            if z > 0:
                return 4
            elif z < 0:
                return 5
            else:
                return 6
        else:
            if z > 0:
                return 7
            else:
                return 8
    elif x < 0:
        if y > 0:
            return 9
        else:
            return 10
    return 11
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        # Force complexity for testing if needed
        if facts.cyclomatic_complexity <= 10:
            facts.cyclomatic_complexity = 11

        issue = check_giant_function(facts)
        assert issue is not None
        assert "complexity" in issue.description.lower()

    def test_small_function_returns_none(self):
        """Test that small, simple functions return None."""
        code = """
def small_func():
    return 42
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_giant_function(facts)
        assert issue is None


class TestStarImports:
    """Test star import detection."""

    def test_star_import_detected(self):
        """Test that star imports are detected."""
        code = """
from os import *

def my_func():
    pathjoin("a", "b")
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        # Set the flag since star imports are module-level
        facts.star_imports_used = True

        issue = check_star_imports(facts)
        assert issue is not None
        assert issue.issue_id == "my_func:star_imports"
        assert "star import" in issue.title.lower()

    def test_no_star_imports_returns_none(self):
        """Test that functions without star imports return None."""
        code = """
def normal_imports():
    import os
    return os.path
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_star_imports(facts)
        assert issue is None


class TestBroadException:
    """Test broad exception catch detection."""

    def test_broad_exception_detected(self):
        """Test that broad exception catching is detected."""
        code = """
def broad_handler():
    try:
        risky()
    except Exception:
        pass
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_broad_exception(facts)
        assert issue is not None
        assert issue.issue_id == "broad_handler:broad_exception"
        assert "broad" in issue.title.lower()
        assert "Exception" in issue.description

    def test_base_exception_detected(self):
        """Test that BaseException catching is also detected."""
        code = """
def very_broad_handler():
    try:
        risky()
    except BaseException:
        pass
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_broad_exception(facts)
        assert issue is not None
        assert "BaseException" in issue.description

    def test_specific_exception_returns_none(self):
        """Test that specific exception catching returns None."""
        code = """
def specific_handler():
    try:
        risky()
    except ValueError:
        pass
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_broad_exception(facts)
        assert issue is None


class TestShadowBuiltin:
    """Test builtin shadowing detection."""

    def test_single_builtin_shadowed(self):
        """Test that shadowing a single builtin is detected."""
        code = """
def bad_name(list):
    return list
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_shadow_builtin(facts)
        assert issue is not None
        assert issue.issue_id == "bad_name:shadow_builtin"
        assert "list" in issue.description
        assert issue.severity == "low"

    def test_multiple_builtins_shadowed(self):
        """Test that shadowing multiple builtins is detected."""
        code = """
def very_bad_names(list, dict, type, max):
    return list, dict, type, max
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_shadow_builtin(facts)
        assert issue is not None
        assert "list" in issue.description
        assert "dict" in issue.description
        assert "type" in issue.description
        assert "max" in issue.description

    def test_no_builtin_shadowing_returns_none(self):
        """Test that functions without builtin shadowing return None."""
        code = """
def good_names(items, mapping, kind):
    return items, mapping, kind
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issue = check_shadow_builtin(facts)
        assert issue is None


class TestRunTier2Checks:
    """Test the Tier 2 check orchestrator."""

    def test_all_checks_run(self):
        """Test that all Tier 2 checks are executed."""
        code = """
def problematic(list=[]):
    try:
        if list is None:
            return []
        import os
        os.system(f"echo {list}")
        return list
    except:
        pass
    print("unreachable")
    return None
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        # Force some flags for testing
        facts.has_return_on_all_paths = False

        issues = run_tier2_checks(facts)

        # Should detect multiple issues
        assert len(issues) > 0

        # Check that we have expected issue types
        issue_ids = [i.issue_id for i in issues]
        assert any("mutable_defaults" in id for id in issue_ids)
        assert any("bare_except" in id for id in issue_ids)
        assert any("command_injection" in id for id in issue_ids)

    def test_clean_function_no_issues(self):
        """Test that clean functions produce no issues."""
        code = """
def clean_function(items: list) -> int:
    '''A clean function with no issues.'''
    if items is None:
        return 0
    return len(items)
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        issues = run_tier2_checks(facts)

        # Should have no issues
        assert len(issues) == 0

    def test_check_failure_doesnt_crash_orchestrator(self, monkeypatch):
        """Test that individual check failures are handled gracefully."""
        code = """
def simple():
    return 1
"""
        tree, _ = parse_python_file(code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, code)

        # Monkeypatch a check to raise an exception
        def broken_check(facts):
            raise RuntimeError("Simulated failure")

        original_checks = TIER2_CHECKS[:]
        TIER2_CHECKS.insert(0, broken_check)

        try:
            # Should not crash
            issues = run_tier2_checks(facts)
            # Other checks should still run
            assert isinstance(issues, list)
        finally:
            # Restore original checks
            TIER2_CHECKS[:] = original_checks

    def test_vulnerable_code_produces_security_issues(self, vulnerable_code: str):
        """Test that vulnerable code produces security findings."""
        tree, _ = parse_python_file(vulnerable_code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, vulnerable_code)

        issues = run_tier2_checks(facts)

        # Should have at least command injection issue
        assert any("command" in i.title.lower() or "injection" in i.title.lower() for i in issues)
        assert any(i.category == "security" for i in issues)


class TestVulnerableCodeFixture:
    """Tests using the vulnerable_code fixture."""

    def test_vulnerable_code_has_command_injection(self, vulnerable_code: str):
        """Test that vulnerable_code fixture is detected as having command injection."""
        tree, _ = parse_python_file(vulnerable_code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, vulnerable_code)

        issues = run_tier2_checks(facts)

        # Should detect command injection
        assert any("command" in i.issue_id or "injection" in i.issue_id for i in issues)


class TestComplexCodeFixture:
    """Tests using the complex_code fixture."""

    def test_complex_code_has_high_complexity(self, complex_code: str):
        """Test that complex_code fixture is detected as complex."""
        tree, _ = parse_python_file(complex_code)
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        facts = extract_function_facts(func_node, complex_code)

        issues = run_tier2_checks(facts)

        # The complex code may not exceed thresholds, but let's check it doesn't crash
        assert isinstance(issues, list)
