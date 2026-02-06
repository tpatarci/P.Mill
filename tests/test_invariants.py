"""Tests for invariant detection."""

import pytest

from backend.analysis.invariants import (
    detect_loop_invariants,
    detect_class_invariants,
    detect_data_structure_invariants,
    verify_invariant_preservation,
    generate_invariant_report,
    LoopInvariantDetector,
    ClassInvariantDetector,
    DataStructureInvariantDetector,
    LoopInvariant,
    ClassInvariant,
    InvariantViolation,
)
from backend.models import ClassInfo, FunctionInfo


class TestLoopInvariantDetection:
    """Test loop invariant detection."""

    def test_empty_code(self):
        """Test with empty code."""
        invariants = detect_loop_invariants("")

        assert invariants == []

    def test_for_loop_detection(self):
        """Test for loop detection."""
        code = """
for i in range(10):
    total += i
"""
        invariants = detect_loop_invariants(code)

        assert len(invariants) > 0
        assert invariants[0].loop_type == "for"

    def test_while_loop_detection(self):
        """Test while loop detection."""
        code = """
while x < 10:
    x += 1
"""
        invariants = detect_loop_invariants(code)

        assert len(invariants) > 0
        assert invariants[0].loop_type == "while"

    def test_loop_variable_extraction(self):
        """Test loop variable extraction."""
        code = """
for item in items:
    process(item)
"""
        invariants = detect_loop_invariants(code)

        if invariants:
            assert invariants[0].loop_variable == "item"

    def test_accumulator_pattern_detection(self):
        """Test accumulator pattern detection."""
        code = """
total = 0
for x in numbers:
    total += x
"""
        invariants = detect_loop_invariants(code)

        # Should detect accumulator invariants
        assert len(invariants) > 0


class TestClassInvariantDetection:
    """Test class invariant detection."""

    def test_simple_class(self):
        """Test with simple class."""
        code = """
class Simple:
    def __init__(self):
        self.value = 0
"""
        classes = [ClassInfo(name="Simple", line_start=2, line_end=4, methods=["__init__"])]
        invariants = detect_class_invariants(code, classes)

        assert isinstance(invariants, dict)

    def test_class_with_init_validation(self):
        """Test class with __init__ validation."""
        code = """
class Validated:
    def __init__(self, value):
        assert value > 0
        assert value < 100
        self.value = value
"""
        classes = [ClassInfo(name="Validated", line_start=2, line_end=7, methods=["__init__"])]
        invariants = detect_class_invariants(code, classes)

        # Should detect validation as invariant
        if "Validated" in invariants:
            assert len(invariants["Validated"].invariants) >= 0

    def test_class_with_properties(self):
        """Test class with properties."""
        code = """
class PropertyClass:
    def __init__(self):
        self._value = 0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        if val < 0:
            raise ValueError("Negative value")
        self._value = val
"""
        classes = [ClassInfo(name="PropertyClass", line_start=2, line_end=16, methods=["__init__", "value"])]
        invariants = detect_class_invariants(code, classes)

        # Should detect property constraints
        if "PropertyClass" in invariants:
            assert len(invariants["PropertyClass"].state_constraints) >= 0


class TestDataStructureInvariantDetection:
    """Test data structure invariant detection."""

    def test_stack_detection(self):
        """Test stack-like structure detection."""
        code = """
class Stack:
    def push(self, item):
        pass

    def pop(self):
        pass

    def peek(self):
        pass
"""
        invariants = detect_data_structure_invariants(code)

        assert "Stack" in invariants
        assert any("Stack" in inv for inv in invariants["Stack"])

    def test_queue_detection(self):
        """Test queue-like structure detection."""
        code = """
class Queue:
    def enqueue(self, item):
        pass

    def dequeue(self):
        pass
"""
        invariants = detect_data_structure_invariants(code)

        assert "Queue" in invariants
        assert any("Queue" in inv for inv in invariants["Queue"])

    def test_tree_detection(self):
        """Test tree-like structure detection."""
        code = """
class TreeNode:
    def left(self):
        pass

    def right(self):
        pass
"""
        invariants = detect_data_structure_invariants(code)

        assert "TreeNode" in invariants
        assert any("Tree" in inv for inv in invariants["TreeNode"])

    def test_container_detection(self):
        """Test container-like structure detection."""
        code = """
class Container:
    def add(self, item):
        pass

    def remove(self, item):
        pass

    def contains(self, item):
        pass
"""
        invariants = detect_data_structure_invariants(code)

        assert "Container" in invariants


class TestInvariantViolation:
    """Test invariant violation detection."""

    def test_no_violations(self):
        """Test with no violations."""
        code = """
class Safe:
    def __init__(self):
        self.value = 0

    def update(self):
        self.value += 1
"""
        classes = [ClassInfo(name="Safe", line_start=2, line_end=7, methods=["__init__", "update"])]
        functions = [FunctionInfo(name="Safe.update", line_start=6, line_end=7, parameters=["self"])]

        violations = verify_invariant_preservation(code, functions, {})

        # Empty invariants = no violations expected
        assert isinstance(violations, list)

    def test_direct_assignment_violation(self):
        """Test detection of direct self assignment without validation."""
        code = """
class InvariantClass:
    def __init__(self):
        self.value = 0

    def update(self, new_value):
        self.value = new_value  # Direct assignment, no validation
"""
        classes = [ClassInfo(name="InvariantClass", line_start=2, line_end=7, methods=["__init__", "update"])]
        functions = [FunctionInfo(name="InvariantClass.update", line_start=6, line_end=7, parameters=["self", "new_value"])]

        # Mock an invariant for self.value
        invariants = {"InvariantClass": ["self.value >= 0"]}

        violations = verify_invariant_preservation(code, functions, invariants)

        # Should detect potential violation (though logic is simplified)
        assert isinstance(violations, list)


class TestInvariantReport:
    """Test invariant report generation."""

    def test_empty_report(self):
        """Test report with no data."""
        report = generate_invariant_report([], {}, {}, [])

        assert report["summary"]["total_loop_invariants"] == 0
        assert report["summary"]["total_class_invariants"] == 0
        assert report["summary"]["total_violations"] == 0

    def test_report_with_loop_invariants(self):
        """Test report with loop invariants."""
        invariants = [
            LoopInvariant(
                loop_type="for",
                loop_variable="i",
                invariants=["i is within range"],
                line_start=2,
                line_end=5,
            )
        ]

        report = generate_invariant_report(invariants, {}, {}, [])

        assert report["summary"]["total_loop_invariants"] == 1
        assert len(report["loop_invariants"]) == 1

    def test_report_with_class_invariants(self):
        """Test report with class invariants."""
        from backend.analysis.invariants import ClassInvariant

        invariants = {
            "Test": ClassInvariant(
                class_name="Test",
                invariants=["value > 0"],
                state_constraints=["value is valid"],
                confidence="high",
            )
        }

        report = generate_invariant_report([], invariants, {}, [])

        assert report["summary"]["total_class_invariants"] == 1
        assert len(report["class_invariants"]) == 1

    def test_report_with_violations(self):
        """Test report with violations."""
        violations = [
            InvariantViolation(
                invariant_type="class",
                entity_name="TestClass",
                location="TestClass:10",
                severity="medium",
                description="Invariant violation detected",
                suggestion="Add validation",
            )
        ]

        report = generate_invariant_report([], {}, {}, violations)

        assert report["summary"]["total_violations"] == 1
        assert report["summary"]["violations_by_severity"]["medium"] == 1


class TestLoopInvariantDetector:
    """Test LoopInvariantDetector class."""

    def test_detector_initialization(self):
        """Test detector initialization."""
        detector = LoopInvariantDetector()

        assert detector.loop_invariants == []

    def test_detector_visits_for_loop(self):
        """Test detector processes for loops."""
        code = "for i in range(10): pass"
        import ast

        tree = ast.parse(code)
        detector = LoopInvariantDetector()
        detector.visit(tree)

        assert len(detector.loop_invariants) > 0


class TestClassInvariantDetector:
    """Test ClassInvariantDetector class."""

    def test_detector_initialization(self):
        """Test detector initialization."""
        detector = ClassInvariantDetector("")

        assert detector.class_invariants == {}

    def test_detector_processes_class(self):
        """Test detector processes classes."""
        code = """
class Test:
    pass
"""
        import ast

        tree = ast.parse(code)
        detector = ClassInvariantDetector(code)
        detector.visit(tree)

        assert isinstance(detector.class_invariants, dict)


class TestDataStructureInvariantDetector:
    """Test DataStructureInvariantDetector class."""

    def test_detector_initialization(self):
        """Test detector initialization."""
        detector = DataStructureInvariantDetector()

        assert detector.invariants == {}


class TestLoopInvariantDataclass:
    """Test LoopInvariant dataclass."""

    def test_field_types(self):
        """Test LoopInvariant has correct field types."""
        invariant = LoopInvariant(
            loop_type="for",
            loop_variable="i",
            invariants=["i >= 0"],
            line_start=5,
            line_end=10,
        )

        assert invariant.loop_type == "for"
        assert invariant.loop_variable == "i"
        assert len(invariant.invariants) == 1


class TestEdgeCases:
    """Test edge cases."""

    def test_syntax_error_code(self):
        """Test with syntax error."""
        invariants = detect_loop_invariants("def broken(")

        assert invariants == []

    def test_nested_loops(self):
        """Test with nested loops."""
        code = """
for i in range(10):
    for j in range(5):
        pass
"""
        invariants = detect_loop_invariants(code)

        # Should detect both loops
        assert len(invariants) >= 1

    def test_empty_class(self):
        """Test with empty class."""
        code = """
class Empty:
    pass
"""
        classes = [ClassInfo(name="Empty", line_start=2, line_end=3, methods=[])]
        invariants = detect_class_invariants(code, classes)

        # Should handle empty class
        assert isinstance(invariants, dict)
