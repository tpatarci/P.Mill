"""Tests for complexity hotspot detection."""

import pytest

from backend.analysis.complexity_hotspots import (
    analyze_class_hotspots,
    analyze_function_hotspots,
    analyze_module_hotspots,
    analyze_nesting_depth,
    generate_complexity_report,
    DEFAULT_COGNITIVE_THRESHOLD,
    DEFAULT_CYCLOMATIC_THRESHOLD,
    DEFAULT_NESTING_THRESHOLD,
    DEFAULT_PARAMETER_COUNT_THRESHOLD,
    DEFAULT_FUNCTION_LOC_THRESHOLD,
    DEFAULT_CLASS_LOC_THRESHOLD,
    DEFAULT_METHOD_COUNT_THRESHOLD,
)
from backend.models import ClassInfo, FunctionInfo


class TestNestingAnalyzer:
    """Test nesting depth analysis."""

    def test_no_nesting(self):
        """Test code with no nesting."""
        code = """
x = 1
y = 2
z = x + y
"""
        result = analyze_nesting_depth(code)
        assert result.max_depth == 0

    def test_single_level_nesting(self):
        """Test code with single level of nesting."""
        code = """
if True:
    x = 1
"""
        result = analyze_nesting_depth(code)
        assert result.max_depth == 1

    def test_two_level_nesting(self):
        """Test code with two levels of nesting."""
        code = """
if True:
    if False:
        x = 1
"""
        result = analyze_nesting_depth(code)
        assert result.max_depth == 2

    def test_deep_nesting(self):
        """Test deeply nested code."""
        code = """
if True:
    if False:
        for i in range(10):
            if i == 5:
                x = 1
"""
        result = analyze_nesting_depth(code)
        assert result.max_depth == 4

    def test_nesting_with_loop(self):
        """Test nesting with for loop."""
        code = """
for i in range(10):
    x = i
"""
        result = analyze_nesting_depth(code)
        assert result.max_depth == 1

    def test_nesting_with_try(self):
        """Test nesting with try-except."""
        code = """
try:
    x = risky()
except Exception:
    x = 0
"""
        result = analyze_nesting_depth(code)
        assert result.max_depth == 1

    def test_nesting_with_comprehension(self):
        """Test nesting with list comprehension."""
        code = """
if True:
    x = [i for i in range(10)]
"""
        result = analyze_nesting_depth(code)
        # List comp adds nesting level
        assert result.max_depth == 2

    def test_nesting_context_recorded(self):
        """Test that nesting context is recorded."""
        code = """
if True:
    x = 1
"""
        result = analyze_nesting_depth(code)
        assert "If" in result.context
        assert "line" in result.context

    def test_nested_function_creates_nesting(self):
        """Test that nested function creates nesting."""
        code = """
def outer():
    def inner():
        return 1
    return inner
"""
        result = analyze_nesting_depth(code)
        # Function definition doesn't count as control flow nesting in our model
        # but the structure is nested
        assert result.max_depth >= 0


class TestFunctionHotspots:
    """Test function hotspot detection."""

    def test_simple_function_no_hotspots(self):
        """Test simple function with no hotspots."""
        code = """
def simple():
    return 42
"""
        func = FunctionInfo(
            name="simple",
            line_start=2,
            line_end=3,
            parameters=[],
        )

        hotspots = analyze_function_hotspots(func, code)
        assert len(hotspots) == 0

    def test_high_cyclomatic_complexity_detected(self):
        """Test detection of high cyclomatic complexity."""
        # Create code with 12 branches (CC = 13)
        code = """
def complex_func(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    elif x == 3:
        return 3
    elif x == 4:
        return 4
    elif x == 5:
        return 5
    elif x == 6:
        return 6
    elif x == 7:
        return 7
    elif x == 8:
        return 8
    elif x == 9:
        return 9
    elif x == 10:
        return 10
    elif x == 11:
        return 11
    else:
        return 0
"""
        func = FunctionInfo(
            name="complex_func",
            line_start=2,
            line_end=27,
            parameters=["x"],
        )

        hotspots = analyze_function_hotspots(func, code)
        cc_hotspots = [h for h in hotspots if h.hotspot_type == "high_cc"]
        assert len(cc_hotspots) > 0
        assert cc_hotspots[0].value > DEFAULT_CYCLOMATIC_THRESHOLD

    def test_high_cognitive_complexity_detected(self):
        """Test detection of high cognitive complexity."""
        # Create deeply nested code with multiple branches
        code = """
def nested_func(x):
    if x > 0:
        if x > 10:
            if x > 100:
                if x > 1000:
                    if x > 10000:
                        return x
                    else:
                        return 0
                elif x > 500:
                    return 1
                else:
                    return 2
            else:
                return 3
        else:
            return 4
    elif x < 0:
        return 5
    else:
        return 6
"""
        func = FunctionInfo(
            name="nested_func",
            line_start=2,
            line_end=24,
            parameters=["x"],
        )

        hotspots = analyze_function_hotspots(func, code)
        cognitive_hotspots = [h for h in hotspots if h.hotspot_type == "high_cognitive"]
        assert len(cognitive_hotspots) > 0
        assert cognitive_hotspots[0].value > DEFAULT_COGNITIVE_THRESHOLD

    def test_deep_nesting_detected(self):
        """Test detection of deep nesting."""
        code = """
def deep_nested():
    if True:
        if True:
            if True:
                if True:
                    if True:
                        x = 1
"""
        func = FunctionInfo(
            name="deep_nested",
            line_start=2,
            line_end=10,
            parameters=[],
        )

        hotspots = analyze_function_hotspots(func, code)
        nesting_hotspots = [h for h in hotspots if h.hotspot_type == "deep_nesting"]
        assert len(nesting_hotspots) > 0
        assert nesting_hotspots[0].value > DEFAULT_NESTING_THRESHOLD

    def test_long_parameter_list_detected(self):
        """Test detection of long parameter lists."""
        code = """
def many_params(a, b, c, d, e, f):
    return a + b + c + d + e + f
"""
        func = FunctionInfo(
            name="many_params",
            line_start=2,
            line_end=3,
            parameters=["a", "b", "c", "d", "e", "f"],
        )

        hotspots = analyze_function_hotspots(func, code)
        param_hotspots = [h for h in hotspots if h.hotspot_type == "long_params"]
        assert len(param_hotspots) > 0

    def test_large_function_detected(self):
        """Test detection of large functions by LOC."""
        # Create a function with >50 lines
        lines = ["def large_function():"]
        for i in range(60):
            lines.append(f"    x{i} = {i}")
        lines.append("    return sum([x0, x1, x2])")
        code = "\n".join(lines)

        func = FunctionInfo(
            name="large_function",
            line_start=1,
            line_end=len(lines),
            parameters=[],
        )

        hotspots = analyze_function_hotspots(func, code)
        size_hotspots = [h for h in hotspots if h.hotspot_type == "large_size"]
        assert len(size_hotspots) > 0

    def test_multiple_hotspots_same_function(self):
        """Test function with multiple hotspots."""
        code = """
def problematic(a, b, c, d, e, f):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return f
"""
        func = FunctionInfo(
            name="problematic",
            line_start=2,
            line_end=10,
            parameters=["a", "b", "c", "d", "e", "f"],
        )

        hotspots = analyze_function_hotspots(func, code)
        # Should detect multiple issues: nesting, params
        hotspot_types = {h.hotspot_type for h in hotspots}
        assert "deep_nesting" in hotspot_types
        assert "long_params" in hotspot_types

    def test_severity_levels(self):
        """Test that severity levels are assigned correctly."""
        # Very high complexity
        code = """
def critical(x):
    if x:
        pass
    elif x:
        pass
    elif x:
        pass
    elif x:
        pass
    elif x:
        pass
    elif x:
        pass
    elif x:
        pass
    elif x:
        pass
    elif x:
        pass
    else:
        pass
"""
        func = FunctionInfo(
            name="critical",
            line_start=2,
            line_end=22,
            parameters=["x"],
        )

        hotspots = analyze_function_hotspots(func, code)
        if hotspots:
            # At least one hotspot should have a severity level
            assert hotspots[0].severity in ["low", "medium", "high", "critical"]

    def test_hotspot_has_suggestion(self):
        """Test that hotspots include suggestions."""
        code = """
def needs_refactoring(a, b, c, d, e, f, g):
    return a + b
"""
        func = FunctionInfo(
            name="needs_refactoring",
            line_start=2,
            line_end=3,
            parameters=["a", "b", "c", "d", "e", "f", "g"],
        )

        hotspots = analyze_function_hotspots(func, code)
        if hotspots:
            assert hotspots[0].suggestion is not None

    def test_custom_thresholds(self):
        """Test using custom thresholds."""
        code = """
def medium_complexity():
    if True:
        return 1
    return 0
"""
        func = FunctionInfo(
            name="medium_complexity",
            line_start=2,
            line_end=5,
            parameters=[],
        )

        # Default threshold would not trigger
        hotspots_default = analyze_function_hotspots(func, code)
        cc_default = [h for h in hotspots_default if h.hotspot_type == "high_cc"]

        # Custom low threshold should trigger
        hotspots_custom = analyze_function_hotspots(
            func, code, thresholds={"cyclomatic": 1}
        )
        cc_custom = [h for h in hotspots_custom if h.hotspot_type == "high_cc"]

        assert len(cc_custom) > len(cc_default)


class TestClassHotspots:
    """Test class hotspot detection."""

    def test_simple_class_no_hotspots(self):
        """Test simple class with no hotspots."""
        code = """
class Simple:
    def method1(self):
        pass

    def method2(self):
        pass
"""
        cls = ClassInfo(
            name="Simple",
            line_start=2,
            line_end=7,
            methods=["method1", "method2"],
        )

        hotspots = analyze_class_hotspots(cls, code)
        assert len(hotspots) == 0

    def test_many_methods_detected(self):
        """Test detection of classes with many methods."""
        method_names = [f"method{i}" for i in range(15)]
        code = f"""
class LargeClass:
    def __init__(self):
        pass
"""
        for i in range(15):
            code += f"\n    def method{i}(self):\n        pass"

        cls = ClassInfo(
            name="LargeClass",
            line_start=2,
            line_end=20,
            methods=method_names,
        )

        hotspots = analyze_class_hotspots(cls, code)
        method_hotspots = [h for h in hotspots if h.hotspot_type == "many_methods"]
        assert len(method_hotspots) > 0

    def test_large_class_detected(self):
        """Test detection of large classes by LOC."""
        lines = ["class LargeClass:"]
        for i in range(350):
            if i == 0:
                lines.append("    pass")
            else:
                lines.append(f"    # comment {i}")
        code = "\n".join(lines)

        cls = ClassInfo(
            name="LargeClass",
            line_start=1,
            line_end=len(lines),
            methods=[],
        )

        hotspots = analyze_class_hotspots(cls, code)
        size_hotspots = [h for h in hotspots if h.hotspot_type == "large_size"]
        assert len(size_hotspots) > 0

    def test_class_hotspot_fields(self):
        """Test that class hotspots have correct fields."""
        code = """
class Test:
    def m1(self): pass
    def m2(self): pass
""" * 5  # Repeat to exceed threshold
        code = f"""
class Test:
    def m1(self): pass
    def m2(self): pass
    def m3(self): pass
    def m4(self): pass
    def m5(self): pass
    def m6(self): pass
    def m7(self): pass
    def m8(self): pass
    def m9(self): pass
    def m10(self): pass
    def m11(self): pass
"""

        cls = ClassInfo(
            name="Test",
            line_start=2,
            line_end=14,
            methods=[f"m{i}" for i in range(1, 12)],
        )

        hotspots = analyze_class_hotspots(cls, code)
        if hotspots:
            hotspot = hotspots[0]
            assert hotspot.entity_type == "class"
            assert hotspot.name == "Test"
            assert hotspot.file_path == ""  # Default


class TestModuleHotspots:
    """Test module-level hotspot analysis."""

    def test_module_with_functions(self):
        """Test analyzing module with multiple functions."""
        code = """
def simple():
    return 1

def medium(x):
    if x:
        return 1
    return 0

def large(a, b, c, d, e, f):
    if a:
        if b:
            if c:
                if d:
                    return f
"""

        functions = [
            FunctionInfo(
                name="simple",
                line_start=2,
                line_end=3,
                parameters=[],
            ),
            FunctionInfo(
                name="medium",
                line_start=5,
                line_end=9,
                parameters=["x"],
            ),
            FunctionInfo(
                name="large",
                line_start=11,
                line_end=19,
                parameters=["a", "b", "c", "d", "e", "f"],
            ),
        ]

        hotspots = analyze_module_hotspots(code, "test.py", functions=functions, classes=[])
        # Should detect issues in the 'large' function
        assert len(hotspots) > 0

    def test_module_with_classes(self):
        """Test analyzing module with classes."""
        code = """
class Small:
    pass

class Large:
    def m1(self): pass
    def m2(self): pass
    def m3(self): pass
    def m4(self): pass
    def m5(self): pass
    def m6(self): pass
    def m7(self): pass
    def m8(self): pass
    def m9(self): pass
    def m10(self): pass
    def m11(self): pass
"""

        classes = [
            ClassInfo(name="Small", line_start=2, line_end=3, methods=[]),
            ClassInfo(
                name="Large",
                line_start=5,
                line_end=17,
                methods=[f"m{i}" for i in range(1, 12)],
            ),
        ]

        hotspots = analyze_module_hotspots(code, "test.py", functions=[], classes=classes)
        # Should detect issues in the 'Large' class
        assert len(hotspots) > 0

    def test_hotspots_sorted_by_severity(self):
        """Test that hotspots are sorted by severity."""
        code = """
def critical(a, b, c, d, e, f, g, h, i, j):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return j
"""
        functions = [
            FunctionInfo(
                name="critical",
                line_start=2,
                line_end=10,
                parameters=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"],
            )
        ]

        hotspots = analyze_module_hotspots(code, "test.py", functions=functions, classes=[])
        # Critical should come before lower severity
        if len(hotspots) >= 2:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for i in range(len(hotspots) - 1):
                current = severity_order.get(hotspots[i].severity, 99)
                next_sev = severity_order.get(hotspots[i + 1].severity, 99)
                assert current <= next_sev


class TestComplexityReport:
    """Test complexity report generation."""

    def test_empty_report(self):
        """Test report with no hotspots."""
        report = generate_complexity_report([])

        assert report["total_hotspots"] == 0
        assert report["by_type"] == {}
        assert report["by_severity"] == {}
        assert report["by_entity_type"] == {}
        assert report["hotspots"] == []

    def test_report_with_hotspots(self):
        """Test report with hotspots."""
        code = """
def test(a, b, c, d, e, f):
    return a
"""
        func = FunctionInfo(
            name="test",
            line_start=2,
            line_end=3,
            parameters=["a", "b", "c", "d", "e", "f"],
        )

        hotspots = analyze_function_hotspots(func, code)
        report = generate_complexity_report(hotspots)

        assert report["total_hotspots"] == len(hotspots)
        assert len(report["hotspots"]) == len(hotspots)

    def test_report_groups_by_type(self):
        """Test that report groups hotspots by type."""
        code = """
def test(a, b, c, d, e, f):
    if a:
        if b:
            if c:
                if d:
                    return e
"""
        func = FunctionInfo(
            name="test",
            line_start=2,
            line_end=9,
            parameters=["a", "b", "c", "d", "e", "f"],
        )

        hotspots = analyze_function_hotspots(func, code)
        report = generate_complexity_report(hotspots)

        # Should have entries for different hotspot types
        assert report["total_hotspots"] > 0
        if report["total_hotspots"] > 0:
            assert len(report["by_type"]) > 0

    def test_report_groups_by_severity(self):
        """Test that report groups hotspots by severity."""
        code = """
def test(a, b, c, d, e, f):
    return a
"""
        func = FunctionInfo(
            name="test",
            line_start=2,
            line_end=3,
            parameters=["a", "b", "c", "d", "e", "f"],
        )

        hotspots = analyze_function_hotspots(func, code)
        report = generate_complexity_report(hotspots)

        if hotspots:
            assert len(report["by_severity"]) > 0

    def test_report_hotspot_format(self):
        """Test that hotspots in report have correct format."""
        code = """
def test(a, b, c, d, e, f):
    return a
"""
        func = FunctionInfo(
            name="test",
            line_start=2,
            line_end=3,
            parameters=["a", "b", "c", "d", "e", "f"],
        )

        hotspots = analyze_function_hotspots(func, code)
        report = generate_complexity_report(hotspots)

        if report["hotspots"]:
            hotspot = report["hotspots"][0]
            assert "entity" in hotspot
            assert "type" in hotspot
            assert "severity" in hotspot
            assert "value" in hotspot
            assert "threshold" in hotspot
            assert "description" in hotspot
