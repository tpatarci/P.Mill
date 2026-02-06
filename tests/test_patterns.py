"""Tests for pattern and anti-pattern detection."""

import pytest

from backend.analysis.patterns import (
    detect_design_patterns,
    detect_anti_patterns,
    generate_pattern_report,
    SingletonPatternDetector,
    FactoryPatternDetector,
    StrategyPatternDetector,
    DecoratorPatternDetector,
    AntiPatternDetector,
    DuplicateCodeDetector,
    PatternMatch,
    AntiPatternMatch,
    CodeSmell,
    DuplicateCodeBlock,
    DEFAULT_DUPLICATE_THRESHOLD,
    DEFAULT_LONG_METHOD_LINES,
    DEFAULT_LARGE_CLASS_LINES,
    DEFAULT_MAGIC_NUMBER_THRESHOLD,
)
from backend.models import ClassInfo, FunctionInfo


class TestSingletonPattern:
    """Test Singleton pattern detection."""

    def test_singleton_via_new(self):
        """Test Singleton via __new__ override."""
        code = """
class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
"""
        patterns = detect_design_patterns(code, [])

        singleton_patterns = [p for p in patterns if p.pattern_type == "singleton"]
        assert len(singleton_patterns) > 0
        assert singleton_patterns[0].entity_name == "Singleton"

    def test_singleton_via_get_instance(self):
        """Test Singleton via getInstance method."""
        code = """
class Singleton:
    _instance = None

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
"""
        patterns = detect_design_patterns(code, [])

        singleton_patterns = [p for p in patterns if p.pattern_type == "singleton"]
        assert len(singleton_patterns) > 0

    def test_no_singleton(self):
        """Test that normal classes aren't detected as Singleton."""
        code = """
class Normal:
    def __init__(self):
        self.value = 42
"""
        patterns = detect_design_patterns(code, [])

        singleton_patterns = [p for p in patterns if p.pattern_type == "singleton"]
        assert len(singleton_patterns) == 0


class TestFactoryPattern:
    """Test Factory pattern detection."""

    def test_factory_class(self):
        """Test Factory class detection."""
        code = """
class Factory:
    def create_product(self, type):
        if type == "A":
            return ProductA()
        elif type == "B":
            return ProductB()
"""
        patterns = detect_design_patterns(code, [])

        factory_patterns = [p for p in patterns if p.pattern_type == "factory"]
        assert len(factory_patterns) > 0

    def test_creator_class(self):
        """Test Creator class detection."""
        code = """
class Creator:
    def make_object(self):
        return Object()
"""
        patterns = detect_design_patterns(code, [])

        factory_patterns = [p for p in patterns if p.pattern_type == "factory"]
        assert len(factory_patterns) > 0

    def test_no_factory(self):
        """Test that normal classes aren't detected as Factory."""
        code = """
class Normal:
    def process(self):
        pass
"""
        patterns = detect_design_patterns(code, [])

        factory_patterns = [p for p in patterns if p.pattern_type == "factory"]
        assert len(factory_patterns) == 0


class TestStrategyPattern:
    """Test Strategy pattern detection."""

    def test_strategy_class(self):
        """Test Strategy class detection."""
        code = """
class SortStrategy:
    def execute(self, data):
        raise NotImplementedError
"""
        patterns = detect_design_patterns(code, [])

        strategy_patterns = [p for p in patterns if p.pattern_type == "strategy"]
        assert len(strategy_patterns) > 0

    def test_abstract_strategy(self):
        """Test abstract Strategy with abstract methods."""
        code = """
class PaymentStrategy:
    def pay(self, amount):
        raise NotImplementedError

    def refund(self, amount):
        raise NotImplementedError
"""
        patterns = detect_design_patterns(code, [])

        strategy_patterns = [p for p in patterns if p.pattern_type == "strategy"]
        assert len(strategy_patterns) > 0

    def test_no_strategy(self):
        """Test that normal classes aren't detected as Strategy."""
        code = """
class Concrete:
    def do_work(self):
        return "working"
"""
        patterns = detect_design_patterns(code, [])

        strategy_patterns = [p for p in patterns if p.pattern_type == "strategy"]
        assert len(strategy_patterns) == 0


class TestDecoratorPattern:
    """Test Decorator pattern detection."""

    def test_decorator_function(self):
        """Test decorator function detection."""
        code = """
def my_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
"""
        patterns = detect_design_patterns(code, [])

        decorator_patterns = [p for p in patterns if p.pattern_type == "decorator"]
        assert len(decorator_patterns) > 0

    def test_named_decorator(self):
        """Test decorator with 'decorator' in name."""
        code = """
def timer_decorator(func):
    def wrapper():
        result = func()
        return result
    return wrapper
"""
        patterns = detect_design_patterns(code, [])

        decorator_patterns = [p for p in patterns if p.pattern_type == "decorator"]
        assert len(decorator_patterns) > 0

    def test_no_decorator(self):
        """Test that normal functions aren't detected as Decorator."""
        code = """
def normal_function(x):
    return x * 2
"""
        patterns = detect_design_patterns(code, [])

        decorator_patterns = [p for p in patterns if p.pattern_type == "decorator"]
        assert len(decorator_patterns) == 0


class TestAntiPatternDetection:
    """Test anti-pattern detection."""

    def test_god_object_detected(self):
        """Test god object detection."""
        # Create a large class
        methods = "\n".join([f"    def method{i}(self): pass" for i in range(20)])
        code = f"""
class GodObject:
    def __init__(self):
        pass
{methods}
"""
        classes = [
            ClassInfo(name="GodObject", line_start=2, line_end=25, methods=[f"method{i}" for i in range(20)])
        ]

        anti_patterns, code_smells = detect_anti_patterns(code, classes, [])

        god_objects = [a for a in anti_patterns if a.anti_pattern_type == "god_object"]
        assert len(god_objects) > 0

    def test_spaghetti_code_detected(self):
        """Test spaghetti code detection (deep nesting)."""
        code = """
def nested():
    if True:
        if True:
            if True:
                if True:
                    if True:
                        pass
"""
        functions = [
            FunctionInfo(name="nested", line_start=2, line_end=9, parameters=[])
        ]

        anti_patterns, code_smells = detect_anti_patterns(code, [], functions)

        spaghetti = [a for a in anti_patterns if a.anti_pattern_type == "spaghetti_code"]
        assert len(spaghetti) > 0

    def test_long_method_detected(self):
        """Test long method detection."""
        lines = ["def long_method():"]
        for i in range(35):
            lines.append(f"    x{i} = {i}")
        code = "\n".join(lines)

        functions = [
            FunctionInfo(name="long_method", line_start=1, line_end=36, parameters=[])
        ]

        anti_patterns, code_smells = detect_anti_patterns(code, [], functions)

        long_methods = [s for s in code_smells if s.smell_type == "long_method"]
        assert len(long_methods) > 0

    def test_normal_class_no_anti_patterns(self):
        """Test that normal classes don't trigger anti-pattern detection."""
        code = """
class Normal:
    def method1(self):
        pass

    def method2(self):
        pass
"""
        classes = [
            ClassInfo(name="Normal", line_start=2, line_end=7, methods=["method1", "method2"])
        ]

        anti_patterns, code_smells = detect_anti_patterns(code, classes, [])

        # Should not have god_object or spaghetti_code
        assert not any(a.anti_pattern_type == "god_object" for a in anti_patterns)
        assert not any(a.anti_pattern_type == "spaghetti_code" for a in anti_patterns)


class TestDuplicateCodeDetection:
    """Test duplicate code detection."""

    def test_duplicate_methods_detected(self):
        """Test detection of duplicate methods."""
        code = """
def method_a():
    x = 1
    y = 2
    z = x + y
    return z

def method_b():
    x = 1
    y = 2
    z = x + y
    return z

def method_c():
    a = 1
    b = 2
    return a + b
"""
        functions = [
            FunctionInfo(name="method_a", line_start=2, line_end=7, parameters=[]),
            FunctionInfo(name="method_b", line_start=9, line_end=14, parameters=[]),
            FunctionInfo(name="method_c", line_start=16, line_end=19, parameters=[]),
        ]

        detector = DuplicateCodeDetector(similarity_threshold=0.7)
        duplicates = detector.detect_duplicates(functions, code)

        assert len(duplicates) > 0
        # method_a and method_b should be detected as duplicates
        assert any("method_a" in str(dup.locations) and "method_b" in str(dup.locations)
                   for dup in duplicates)

    def test_no_duplicates_simple(self):
        """Test that different methods aren't flagged."""
        code = """
def method_a():
    x = 100
    y = 200
    z = x + y + 500
    return z * 2

def method_b():
    result = calculate()
    return process(result)
"""
        functions = [
            FunctionInfo(name="method_a", line_start=2, line_end=7, parameters=[]),
            FunctionInfo(name="method_b", line_start=9, line_end=11, parameters=[]),
        ]

        detector = DuplicateCodeDetector()
        duplicates = detector.detect_duplicates(functions, code)

        assert len(duplicates) == 0


class TestPatternReport:
    """Test pattern report generation."""

    def test_empty_report(self):
        """Test report with no patterns."""
        report = generate_pattern_report([], [], [])

        assert report["summary"]["design_patterns_found"] == 0
        assert report["summary"]["anti_patterns_found"] == 0
        assert report["summary"]["code_smells_found"] == 0

    def test_report_with_patterns(self):
        """Test report with design patterns."""
        patterns = [
            PatternMatch(
                pattern_type="singleton",
                entity_name="MySingleton",
                line_start=1,
                line_end=10,
                confidence="high",
                description="Singleton pattern",
                evidence=["_instance var"],
            )
        ]

        report = generate_pattern_report(patterns, [], [])

        assert report["summary"]["design_patterns_found"] == 1
        assert "singleton" in report["summary"]["by_pattern_type"]
        assert len(report["design_patterns"]) == 1

    def test_report_with_anti_patterns(self):
        """Test report with anti-patterns."""
        anti_patterns = [
            AntiPatternMatch(
                anti_pattern_type="god_object",
                entity_name="BigClass",
                severity="high",
                line_start=1,
                line_end=100,
                description="Very large class",
                suggestion="Split it up",
            )
        ]

        report = generate_pattern_report([], anti_patterns, [])

        assert report["summary"]["anti_patterns_found"] == 1
        assert "god_object" in report["summary"]["by_anti_pattern_type"]
        assert report["summary"]["by_severity"]["high"] == 1

    def test_report_with_code_smells(self):
        """Test report with code smells."""
        code_smells = [
            CodeSmell(
                smell_type="long_method",
                entity_name="big_method",
                location="big_method:10",
                severity="medium",
                description="Method is too long",
                suggestion="Break it up",
            )
        ]

        report = generate_pattern_report([], [], code_smells)

        assert report["summary"]["code_smells_found"] == 1
        assert "long_method" in report["summary"]["by_smell_type"]
        assert len(report["code_smells"]) == 1

    def test_report_severity_aggregation(self):
        """Test that severities are aggregated correctly."""
        anti_patterns = [
            AntiPatternMatch(
                anti_pattern_type="test",
                entity_name="A",
                severity="high",
                line_start=1,
                line_end=10,
                description="Test",
                suggestion="Fix it",
            ),
            AntiPatternMatch(
                anti_pattern_type="test",
                entity_name="B",
                severity="high",
                line_start=11,
                line_end=20,
                description="Test",
                suggestion="Fix it",
            ),
            AntiPatternMatch(
                anti_pattern_type="test",
                entity_name="C",
                severity="low",
                line_start=21,
                line_end=30,
                description="Test",
                suggestion="Fix it",
            ),
        ]

        report = generate_pattern_report([], anti_patterns, [])

        assert report["summary"]["by_severity"]["high"] == 2
        assert report["summary"]["by_severity"]["low"] == 1


class TestPatternMatch:
    """Test PatternMatch dataclass."""

    def test_pattern_match_fields(self):
        """Test that PatternMatch has all required fields."""
        match = PatternMatch(
            pattern_type="test",
            entity_name="TestEntity",
            line_start=1,
            line_end=10,
            confidence="high",
            description="Test pattern",
            evidence=["evidence1", "evidence2"],
        )

        assert match.pattern_type == "test"
        assert match.entity_name == "TestEntity"
        assert match.line_start == 1
        assert match.line_end == 10
        assert match.confidence == "high"
        assert match.description == "Test pattern"
        assert len(match.evidence) == 2


class TestAntiPatternMatch:
    """Test AntiPatternMatch dataclass."""

    def test_anti_pattern_match_fields(self):
        """Test that AntiPatternMatch has all required fields."""
        match = AntiPatternMatch(
            anti_pattern_type="test",
            entity_name="TestEntity",
            severity="high",
            line_start=1,
            line_end=10,
            description="Test anti-pattern",
            suggestion="Fix it",
        )

        assert match.anti_pattern_type == "test"
        assert match.entity_name == "TestEntity"
        assert match.severity == "high"
        assert match.line_start == 1
        assert match.line_end == 10
        assert match.description == "Test anti-pattern"
        assert match.suggestion == "Fix it"


class TestThresholdConstants:
    """Test threshold constants."""

    def test_thresholds_defined(self):
        """Test that threshold constants are defined."""
        assert 0 < DEFAULT_DUPLICATE_THRESHOLD <= 1
        assert DEFAULT_LONG_METHOD_LINES > 0
        assert DEFAULT_LARGE_CLASS_LINES > 0
        assert DEFAULT_MAGIC_NUMBER_THRESHOLD > 0
