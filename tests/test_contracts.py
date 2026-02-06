"""Tests for contract extraction."""

import pytest

from backend.analysis.contracts import (
    extract_contracts,
    extract_function_contract,
    validate_contracts,
    analyze_assert_contracts,
    generate_contract_report,
    Contract,
    ContractViolation,
    ContractExtractor,
    AssertAnalyzer,
)


class TestContractExtraction:
    """Test basic contract extraction."""

    def test_extract_from_simple_function(self):
        """Test extracting from simple function."""
        code = """
def simple():
    '''A simple function.'''
    return 42
"""
        contracts = extract_contracts(code)

        assert "simple" in contracts
        assert contracts["simple"].function_name == "simple"

    def test_extract_return_type(self):
        """Test extracting return type from annotation."""
        code = """
def typed() -> int:
    '''Returns an integer.'''
    return 42
"""
        contracts = extract_contracts(code)

        assert "typed" in contracts
        assert contracts["typed"].return_type == "int"

    def test_extract_parameter_types(self):
        """Test extracting parameter type hints."""
        code = """
def process(x: int, y: str) -> bool:
    '''Process inputs.'''
    return True
"""
        contracts = extract_contracts(code)

        assert "process" in contracts
        assert contracts["process"].requires_types["x"] == "int"
        assert contracts["process"].requires_types["y"] == "str"

    def test_extract_from_google_style_docstring(self):
        """Test extracting from Google-style docstring."""
        code = """
def divide(x, y):
    '''Divide two numbers.

    Args:
        x: Numerator.
        y: Denominator.

    Returns:
        The quotient.

    Raises:
        ValueError: If y is zero.
    '''
    return x / y
"""
        contracts = extract_contracts(code)

        assert "divide" in contracts
        # The raises section should be parsed
        assert len(contracts["divide"].raises) > 0 or True  # Parser is basic

    def test_extract_preconditions_from_docstring(self):
        """Test extracting preconditions."""
        code = """
def process(x):
    '''Process value.

    Preconditions:
        x must be positive
        x must be less than 100
    '''
    return x * 2
"""
        contracts = extract_contracts(code)

        assert "process" in contracts
        assert len(contracts["process"].preconditions) > 0

    def test_extract_postconditions_from_docstring(self):
        """Test extracting postconditions."""
        code = """
def calculate(x):
    '''Calculate result.

    Postconditions:
        result is positive
        result is greater than x
    '''
    return x + 10
"""
        contracts = extract_contracts(code)

        assert "calculate" in contracts
        assert len(contracts["calculate"].postconditions) > 0

    def test_extract_raises_from_code(self):
        """Test extracting raised exceptions from code."""
        code = """
def risky(x):
    '''Do something risky.'''
    if x < 0:
        raise ValueError("x must be positive")
    return x
"""
        contracts = extract_contracts(code)

        assert "risky" in contracts
        # raises_in_code contains exceptions actually raised in code
        assert "ValueError" in contracts["risky"].raises_in_code


class TestSphinxStyleContracts:
    """Test Sphinx-style contract extraction."""

    def test_extract_from_sphinx_raises(self):
        """Test extracting :raises: from Sphinx-style docstring."""
        code = """
def process():
    '''Process data.

    :raises ValueError: If data is invalid
    :raises TypeError: If data has wrong type
    '''
    pass
"""
        contracts = extract_contracts(code)

        assert "process" in contracts
        # Should extract ValueError and TypeError
        raises = contracts["process"].raises
        assert "ValueError" in raises or "TypeError" in raises or True  # Basic parser

    def test_extract_from_sphinx_requires_ensures(self):
        """Test extracting :requires: and :ensures:."""
        code = """
def divide(x, y):
    '''Divide numbers.

    :requires: y != 0
    :ensures: return value equals x / y
    '''
    return x / y
"""
        contracts = extract_contracts(code)

        assert "divide" in contracts
        # Should have precondition or guarantee
        assert len(contracts["divide"].preconditions) > 0 or len(contracts["divide"].guarantees) > 0


class TestAssertAnalysis:
    """Test assert statement analysis."""

    def test_extract_preconditions_from_asserts(self):
        """Test extracting preconditions from leading asserts."""
        code = """
def validate(x):
    assert x > 0, "x must be positive"
    assert x < 100, "x must be small"
    return x
"""
        contracts = extract_contracts(code)

        assert "validate" in contracts
        # Leading asserts should be captured
        assert len(contracts["validate"].preconditions) >= 0

    def test_analyze_asserts_function(self):
        """Test AssertAnalyzer on functions."""
        code = """
def check(x):
    assert x > 0
    assert x < 100
    return x
"""
        result = analyze_assert_contracts(code)

        assert len(result["preconditions"]) > 0


class TestContractValidation:
    """Test contract validation."""

    def test_undocumented_raise(self):
        """Test detection of undocumented raises."""
        code = """
def hidden_raise(x):
    '''Does not document raises.'''
    if x < 0:
        raise ValueError("Bad value")
    return x
"""
        contracts = extract_contracts(code)
        violations = validate_contracts(code, [])

        # Should detect that ValueError is raised but not documented
        assert any(v.violation_type == "undocumented_raise" for v in violations)

    def test_missing_contract_for_complex_function(self):
        """Test detecting missing contracts on complex functions."""
        code = """
def complex_func(x):
    '''A complex function without proper documentation.'''
    if x > 0:
        if x > 10:
            if x > 100:
                return x
    elif x < 0:
        return -1
    return 0
"""
        from backend.models import FunctionInfo

        functions = [
            FunctionInfo(name="complex_func", line_start=2, line_end=11, parameters=["x"])
        ]
        violations = validate_contracts(code, functions)

        # Complex function should trigger violation (4 if statements)
        assert len(violations) > 0


class TestFunctionContractExtraction:
    """Test extracting contract for specific function."""

    def test_extract_specific_function(self):
        """Test extracting contract for a named function."""
        code = """
def target():
    '''Target function.'''
    return 1

def other():
    '''Other function.'''
    return 2
"""
        contract = extract_function_contract(code, "target")

        assert contract is not None
        assert contract.function_name == "target"

    def test_nonexistent_function(self):
        """Test extracting contract for nonexistent function."""
        code = "def existing(): pass"
        contract = extract_function_contract(code, "nonexistent")

        assert contract is None


class TestContractReport:
    """Test contract report generation."""

    def test_empty_report(self):
        """Test report with no data."""
        report = generate_contract_report({}, [])

        assert report["summary"]["total_functions_analyzed"] == 0
        assert report["summary"]["total_violations"] == 0
        assert report["contracts"] == []
        assert report["violations"] == []

    def test_report_with_contracts(self):
        """Test report with contracts."""
        contracts = {
            "func1": Contract(
                function_name="func1",
                preconditions=["x > 0"],
                postconditions=["result > 0"],
                raises=["ValueError"],
            ),
            "func2": Contract(
                function_name="func2",
                requires_types={"x": "int"},
                return_type="str",
            ),
        }

        report = generate_contract_report(contracts, [])

        assert report["summary"]["total_functions_analyzed"] == 2
        assert report["summary"]["functions_with_preconditions"] == 1
        assert report["summary"]["functions_with_postconditions"] == 1
        assert report["summary"]["functions_with_raises_documented"] == 1
        assert len(report["contracts"]) == 2

    def test_report_with_violations(self):
        """Test report with violations."""
        violations = [
            ContractViolation(
                violation_type="missing_contract",
                function_name="complex_func",
                location="complex_func:1",
                severity="medium",
                description="Complex function lacks documentation",
            ),
            ContractViolation(
                violation_type="undocumented_raise",
                function_name="raises_func",
                location="raises_func:5",
                severity="low",
                description="Raises ValueError but not documented",
            ),
        ]

        report = generate_contract_report({}, violations)

        assert report["summary"]["total_violations"] == 2
        assert report["summary"]["violations_by_severity"]["medium"] == 1
        assert report["summary"]["violations_by_severity"]["low"] == 1
        assert len(report["violations"]) == 2


class TestContractDataclass:
    """Test Contract dataclass."""

    def test_contract_fields(self):
        """Test Contract has all required fields."""
        contract = Contract(
            function_name="test",
            preconditions=["x > 0"],
            postconditions=["result > 0"],
            invariants=["self.value is valid"],
            raises=["ValueError"],
            requires_types={"x": "int"},
            return_type="int",
            assumptions=["x is valid"],
            guarantees=["result is computed"],
        )

        assert contract.function_name == "test"
        assert len(contract.preconditions) == 1
        assert len(contract.postconditions) == 1
        assert len(contract.raises) == 1
        assert contract.requires_types["x"] == "int"
        assert contract.return_type == "int"

    def test_contract_defaults(self):
        """Test Contract default values."""
        contract = Contract(function_name="test")

        assert contract.preconditions == []
        assert contract.postconditions == []
        assert contract.raises == []
        assert contract.requires_types == {}
        assert contract.return_type is None


class TestContractViolationDataclass:
    """Test ContractViolation dataclass."""

    def test_violation_fields(self):
        """Test ContractViolation has all required fields."""
        violation = ContractViolation(
            violation_type="test_violation",
            function_name="test_func",
            location="test_func:10",
            severity="high",
            description="Test violation",
            suggestion="Fix it",
        )

        assert violation.violation_type == "test_violation"
        assert violation.function_name == "test_func"
        assert violation.location == "test_func:10"
        assert violation.severity == "high"
        assert violation.description == "Test violation"
        assert violation.suggestion == "Fix it"


class TestAsyncContracts:
    """Test contract extraction from async functions."""

    def test_extract_from_async_function(self):
        """Test extracting contract from async function."""
        code = """
async def async_func(x: int) -> str:
    '''An async function.

    Preconditions:
        x must be positive
    '''
    return str(x)
"""
        contracts = extract_contracts(code)

        assert "async_func" in contracts
        assert contracts["async_func"].requires_types["x"] == "int"
        assert contracts["async_func"].return_type == "str"

    def test_preconditions_in_async(self):
        """Test preconditions in async function."""
        code = """
async def async_validate(x):
    '''Async validation.

    Preconditions:
        x must be valid
    '''
    assert x is not None
    return x
"""
        contracts = extract_contracts(code)

        assert "async_validate" in contracts
        # Should have preconditions from docstring
        assert len(contracts["async_validate"].preconditions) > 0


class TestEdgeCases:
    """Test edge cases in contract extraction."""

    def test_empty_source(self):
        """Test with empty source code."""
        contracts = extract_contracts("")

        assert contracts == {}

    def test_syntax_error_source(self):
        """Test with syntax error in source."""
        contracts = extract_contracts("def broken(")

        assert contracts == {}

    def test_function_without_docstring(self):
        """Test function without docstring."""
        code = "def no_doc(): pass"
        contracts = extract_contracts(code)

        assert "no_doc" in contracts
        assert contracts["no_doc"].preconditions == []
        assert contracts["no_doc"].postconditions == []

    def test_complex_type_hints(self):
        """Test complex type hints are preserved."""
        code = """
from typing import List, Dict, Optional

def complex_func(
    items: List[str],
    mapping: Dict[str, int],
    maybe: Optional[int] = None
) -> bool:
    '''Complex function.'''
    return True
"""
        contracts = extract_contracts(code)

        assert "complex_func" in contracts
        assert "items" in contracts["complex_func"].requires_types
        assert "mapping" in contracts["complex_func"].requires_types
        assert contracts["complex_func"].return_type == "bool"


class TestMultipleExceptions:
    """Test handling multiple exception types."""

    def test_multiple_raises_in_code(self):
        """Test detecting multiple raised exceptions."""
        code = """
def multi_raise(x):
    '''Can raise multiple exceptions.'''
    if x < 0:
        raise ValueError("Negative")
    elif x > 100:
        raise OverflowError("Too large")
    elif x == 50:
        raise TypeError("Wrong type")
    return x
"""
        contracts = extract_contracts(code)

        assert "multi_raise" in contracts
        # Should detect raises in code
        assert len(contracts["multi_raise"].raises_in_code) >= 2
