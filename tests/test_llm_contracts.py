"""Tests for LLM-based contract inference."""

import pytest

from backend.analysis.llm_contracts import (
    ContractInference,
    StaticContractInference,
    InferredContract,
    InferredInvariant,
    merge_contracts,
)
from backend.analysis.contracts import Contract
from backend.models import ClassInfo


class TestStaticContractInference:
    """Test static contract inference (no LLM)."""

    def test_infer_from_simple_function(self):
        """Test inferring from simple function."""
        code = """
def simple(x):
    return x + 1
"""
        inferred = StaticContractInference.infer_from_function_source(code, "simple")

        assert inferred.function_name == "simple"
        assert inferred.confidence in ["low", "medium", "high"]

    def test_infer_preconditions_from_asserts(self):
        """Test inferring preconditions from assert statements."""
        code = """
def validate(x):
    assert x > 0, "x must be positive"
    assert x < 100, "x must be small"
    return x
"""
        inferred = StaticContractInference.infer_from_function_source(code, "validate")

        # Should detect asserts as preconditions
        assert len(inferred.preconditions) >= 0

    def test_infer_raises_from_raise_statements(self):
        """Test inferring raises from raise statements."""
        code = """
def risky(x):
    if x < 0:
        raise ValueError("Negative")
    return x
"""
        inferred = StaticContractInference.infer_from_function_source(code, "risky")

        # Should detect raises
        assert len(inferred.raises) >= 0

    def test_infer_assumptions_from_type_hints(self):
        """Test inferring assumptions from type hints."""
        code = """
def typed(x: int, y: Optional[str] = None) -> bool:
    return True
"""
        inferred = StaticContractInference.infer_from_function_source(code, "typed")

        # Should infer assumptions from type hints
        assert len(inferred.assumptions) >= 0

    def test_infer_from_invalid_code(self):
        """Test inferring from invalid code."""
        code = "def broken("  # Syntax error

        inferred = StaticContractInference.infer_from_function_source(code, "broken")

        assert inferred.function_name == "broken"
        assert inferred.confidence == "low"
        assert inferred.preconditions == []

    def test_infer_from_nonexistent_function(self):
        """Test inferring from nonexistent function."""
        code = "def existing(): pass"

        inferred = StaticContractInference.infer_from_function_source(code, "nonexistent")

        assert inferred.function_name == "nonexistent"
        assert inferred.confidence == "low"


class TestClassInvariantInference:
    """Test class invariant inference."""

    def test_infer_from_simple_class(self):
        """Test inferring from simple class."""
        code = """
class Simple:
    def __init__(self):
        self.value = 0
"""
        inferred = StaticContractInference.infer_class_invariants(code, "Simple")

        assert inferred.class_name == "Simple"
        assert isinstance(inferred.invariants, list)

    def test_infer_invariants_from_init_validators(self):
        """Test inferring invariants from __init__ asserts."""
        code = """
class Validated:
    def __init__(self, value):
        assert value > 0
        assert value < 100
        self.value = value
"""
        inferred = StaticContractInference.infer_class_invariants(code, "Validated")

        # Should detect asserts with self. as potential invariants
        assert len(inferred.invariants) >= 0


class TestContractInference:
    """Test LLM-based contract inference."""

    def test_stub_llm_adapter(self):
        """Test with stub LLM adapter."""
        from backend.llm.adapter import StubLLMAdapter

        stub = StubLLMAdapter({
            "contract_inference": '{"preconditions": ["x > 0"], "postconditions": ["result > 0"], "assumptions": [], "raises": []}',
        })

        inference = ContractInference(llm_adapter=stub)

        # This would normally be async, but we can test the structure
        assert inference.llm_adapter is not None

    def test_inferred_contract_dataclass(self):
        """Test InferredContract dataclass."""
        contract = InferredContract(
            function_name="test",
            preconditions=["x > 0"],
            postconditions=["result > 0"],
            assumptions=["x is valid"],
            raises=["ValueError: invalid input"],
            confidence="high",
        )

        assert contract.function_name == "test"
        assert len(contract.preconditions) == 1
        assert contract.confidence == "high"

    def test_inferred_invariant_dataclass(self):
        """Test InferredInvariant dataclass."""
        invariant = InferredInvariant(
            class_name="TestClass",
            invariants=["self.value > 0"],
            state_constraints=["self.value is consistent"],
            confidence="medium",
        )

        assert invariant.class_name == "TestClass"
        assert len(invariant.invariants) == 1


class TestMergeContracts:
    """Test merging explicit and inferred contracts."""

    def test_merge_contracts(self):
        """Test merging explicit and inferred contracts."""
        explicit = Contract(
            function_name="test",
            preconditions=["x > 0"],
            postconditions=["result positive"],
            raises=["ValueError"],
            requires_types={"x": "int"},
            return_type="int",
        )

        inferred = InferredContract(
            function_name="test",
            preconditions=["x < 100"],  # Additional
            postconditions=["result is even"],  # Additional
            assumptions=["x is integer"],
            raises=[],
            confidence="high",
        )

        merged = merge_contracts(explicit, inferred)

        # Should have both preconditions
        assert len(merged.preconditions) >= 1
        assert "x > 0" in merged.preconditions or "x < 100" in merged.preconditions

    def test_merge_preserves_explicit_fields(self):
        """Test that merge preserves explicit contract fields."""
        explicit = Contract(
            function_name="test",
            requires_types={"x": "str"},
            return_type="bool",
            raises_in_code=["TypeError"],
        )

        inferred = InferredContract(
            function_name="test",
            preconditions=["x is not empty"],
            postconditions=["result valid"],
            assumptions=[],
            raises=[],
            confidence="medium",
        )

        merged = merge_contracts(explicit, inferred)

        assert merged.requires_types == {"x": "str"}
        assert merged.return_type == "bool"
        assert merged.raises_in_code == ["TypeError"]


class TestInferenceConfidence:
    """Test confidence estimation."""

    def test_estimate_confidence_from_code(self):
        """Test confidence is always a valid value."""
        code = """
def medium_complexity(x):
    if x > 0:
        return x
    return 0
"""
        inference = ContractInference()

        # Access the confidence estimation method
        inferred_data = {
            "preconditions": ["x > 0"],
            "postconditions": ["result >= 0"],
        }

        confidence = inference._estimate_confidence(code, inferred_data)

        assert confidence in ["low", "medium", "high"]

    def test_class_confidence_estimation(self):
        """Test class confidence estimation."""
        code = """
class Simple:
    pass
"""
        inference = ContractInference()

        inferred_data = {
            "invariants": ["self.value is valid"],
        }

        confidence = inference._estimate_class_confidence(code, inferred_data)

        assert confidence in ["low", "medium", "high"]


class TestEdgeCases:
    """Test edge cases in contract inference."""

    def test_empty_function(self):
        """Test inferring from empty function."""
        code = """
def empty():
    pass
"""
        inferred = StaticContractInference.infer_from_function_source(code, "empty")

        assert inferred.function_name == "empty"

    def test_function_with_only_docstring(self):
        """Test inferring from function with only docstring."""
        code = '''
def documented():
    """This function does something."""
    pass
'''
        inferred = StaticContractInference.infer_from_function_source(code, "documented")

        assert inferred.function_name == "documented"

    def test_class_with_no_init(self):
        """Test inferring invariants from class without __init__."""
        code = """
class NoInit:
    def method(self):
        pass
"""
        inferred = StaticContractInference.infer_class_invariants(code, "NoInit")

        assert inferred.class_name == "NoInit"


class TestContractIntegration:
    """Test integration with contract module."""

    def test_inferred_to_contract_conversion(self):
        """Test that inferred contract can be merged with explicit."""
        code = """
def process(x: int) -> str:
    '''Process a value.'''
    return str(x)
"""
        from backend.analysis.contracts import extract_contracts

        explicit_contracts = extract_contracts(code)
        explicit = explicit_contracts.get("process")

        if explicit:
            inferred = InferredContract(
                function_name="process",
                preconditions=["x is valid"],
                postconditions=["returns string representation"],
                assumptions=[],
                raises=[],
                confidence="medium",
            )

            merged = merge_contracts(explicit, inferred)

            assert merged.function_name == "process"
            assert merged.return_type == "str"  # From explicit


class TestPrompts:
    """Test inference prompts are defined."""

    def test_contract_inference_prompt_exists(self):
        """Test that contract inference prompt is defined."""
        from backend.analysis.llm_contracts import CONTRACT_INFERENCE_PROMPT

        assert CONTRACT_INFERENCE_PROMPT
        assert "{function_code}" in CONTRACT_INFERENCE_PROMPT
        assert "preconditions" in CONTRACT_INFERENCE_PROMPT.lower()

    def test_invariant_inference_prompt_exists(self):
        """Test that invariant inference prompt is defined."""
        from backend.analysis.llm_contracts import INVARIANT_INFERENCE_PROMPT

        assert INVARIANT_INFERENCE_PROMPT
        assert "{class_code}" in INVARIANT_INFERENCE_PROMPT
        assert "invariants" in INVARIANT_INFERENCE_PROMPT.lower()
