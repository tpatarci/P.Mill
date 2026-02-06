"""Tests for cross-validator of LLM results against AST facts."""

import pytest

from backend.models import FindingConfidence, FunctionFacts, ParameterInfo
from backend.pipeline.cross_validator import (
    cross_validate_exception_handling,
    cross_validate_has_return_on_all_paths,
    cross_validate_null_safety,
)


class TestCrossValidateNullSafety:
    """Test null safety cross-validation."""

    def test_unclear_returns_no_data(self):
        """Test UNCLEAR response returns no_data."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[ParameterInfo(name="x", type_hint=None, has_default=False)],
            has_none_checks=[],
        )

        confidence, result = cross_validate_null_safety("UNCLEAR", [], facts)

        assert confidence == FindingConfidence.INCONCLUSIVE
        assert result == "no_data"

    def test_safe_with_all_checks_confirmed(self):
        """Test SAFE with all params having None checks → confirmed."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[
                ParameterInfo(name="x", type_hint=None, has_default=False),
                ParameterInfo(name="y", type_hint=None, has_default=False),
            ],
            has_none_checks=["x", "y"],
        )

        confidence, result = cross_validate_null_safety("SAFE", [], facts)

        assert confidence == FindingConfidence.HIGH
        assert result == "confirmed"

    def test_safe_with_missing_checks_contradicted(self):
        """Test SAFE but some params lack None checks → contradicted."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[
                ParameterInfo(name="x", type_hint=None, has_default=False),
                ParameterInfo(name="y", type_hint=None, has_default=False),
            ],
            has_none_checks=["x"],  # Only x has check, y doesn't
        )

        confidence, result = cross_validate_null_safety("SAFE", [], facts)

        assert confidence == FindingConfidence.LOW
        assert result == "contradicted"

    def test_unsafe_with_missing_checks_confirmed(self):
        """Test UNSAFE and params lack None checks → confirmed."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[
                ParameterInfo(name="data", type_hint=None, has_default=False),
            ],
            has_none_checks=[],  # No checks
        )

        confidence, result = cross_validate_null_safety("UNSAFE", ["data"], facts)

        assert confidence == FindingConfidence.HIGH
        assert result == "confirmed"

    def test_unsafe_with_checks_contradicted(self):
        """Test UNSAFE but params have None checks → contradicted (false positive)."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[
                ParameterInfo(name="data", type_hint=None, has_default=False),
            ],
            has_none_checks=["data"],  # Has check
        )

        confidence, result = cross_validate_null_safety("UNSAFE", ["data"], facts)

        assert confidence == FindingConfidence.LOW
        assert result == "contradicted"

    def test_unsafe_multiple_params_some_checked(self):
        """Test UNSAFE with multiple params, some checked, some not."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[
                ParameterInfo(name="x", type_hint=None, has_default=False),
                ParameterInfo(name="y", type_hint=None, has_default=False),
                ParameterInfo(name="z", type_hint=None, has_default=False),
            ],
            has_none_checks=["x"],  # Only x is checked
        )

        # If LLM says y and z are unsafe (correct), confirmed
        confidence, result = cross_validate_null_safety("UNSAFE", ["y", "z"], facts)

        assert confidence == FindingConfidence.HIGH
        assert result == "confirmed"

        # If LLM says x is unsafe (wrong, x has check), contradicted
        confidence, result = cross_validate_null_safety("UNSAFE", ["x"], facts)

        assert confidence == FindingConfidence.LOW
        assert result == "contradicted"


class TestCrossValidateReturnPaths:
    """Test return path cross-validation."""

    def test_unclear_returns_no_data(self):
        """Test UNCLEAR returns no_data."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[],
            has_return_on_all_paths=True,
        )

        confidence, result = cross_validate_has_return_on_all_paths("UNCLEAR", facts)

        assert confidence == FindingConfidence.INCONCLUSIVE
        assert result == "no_data"

    def test_safe_with_returns_confirmed(self):
        """Test SAFE with returns on all paths → confirmed."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[],
            has_return_on_all_paths=True,
        )

        confidence, result = cross_validate_has_return_on_all_paths("SAFE", facts)

        assert confidence == FindingConfidence.HIGH
        assert result == "confirmed"

    def test_unsafe_without_returns_confirmed(self):
        """Test UNSAFE without returns on all paths → confirmed."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[],
            has_return_on_all_paths=False,
        )

        confidence, result = cross_validate_has_return_on_all_paths("UNSAFE", facts)

        assert confidence == FindingConfidence.HIGH
        assert result == "confirmed"

    def test_safe_without_returns_contradicted(self):
        """Test SAFE but no returns → contradicted."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[],
            has_return_on_all_paths=False,
        )

        confidence, result = cross_validate_has_return_on_all_paths("SAFE", facts)

        assert confidence == FindingConfidence.LOW
        assert result == "contradicted"


class TestCrossValidateExceptionHandling:
    """Test exception handling cross-validation."""

    def test_bare_except_detected_confirmed(self):
        """Test bare except detected by LLM and AST → confirmed."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[],
            has_bare_except=True,
        )

        confidence, result = cross_validate_exception_handling("bare except issue", facts)

        assert confidence == FindingConfidence.HIGH
        assert result == "confirmed"

    def test_bare_except_not_detected_contradicted(self):
        """Test LLM says bare except but AST disagrees → contradicted."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[],
            has_bare_except=False,
        )

        confidence, result = cross_validate_exception_handling("bare except issue", facts)

        assert confidence == FindingConfidence.LOW
        assert result == "contradicted"

    def test_broad_except_detected_confirmed(self):
        """Test broad except detected by LLM and AST → confirmed."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[],
            has_broad_except=True,
        )

        confidence, result = cross_validate_exception_handling("broad exception handling", facts)

        assert confidence == FindingConfidence.HIGH
        assert result == "confirmed"

    def test_unclear_returns_no_data(self):
        """Test unclear response returns no_data."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[],
            has_bare_except=False,
        )

        confidence, result = cross_validate_exception_handling("UNCLEAR", facts)

        assert confidence == FindingConfidence.INCONCLUSIVE
        assert result == "no_data"


class TestCrossValidatorScenarios:
    """Test the 5 main cross-validation scenarios from the spec."""

    def test_scenario_1_unclear_no_data(self):
        """Scenario 1: UNCLEAR → no_data."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[ParameterInfo(name="x", type_hint=None, has_default=False)],
            has_none_checks=[],
        )

        confidence, result = cross_validate_null_safety("UNCLEAR", [], facts)

        assert confidence == FindingConfidence.INCONCLUSIVE
        assert result == "no_data"

    def test_scenario_2_safe_confirmed(self):
        """Scenario 2: SAFE + AST confirms → confirmed."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[ParameterInfo(name="x", type_hint=None, has_default=False)],
            has_none_checks=["x"],
        )

        confidence, result = cross_validate_null_safety("SAFE", [], facts)

        assert confidence == FindingConfidence.HIGH
        assert result == "confirmed"

    def test_scenario_3_safe_contradicted(self):
        """Scenario 3: SAFE + AST contradicts → contradicted."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[ParameterInfo(name="x", type_hint=None, has_default=False)],
            has_none_checks=[],  # No checks, but LLM says SAFE
        )

        confidence, result = cross_validate_null_safety("SAFE", [], facts)

        assert confidence == FindingConfidence.LOW
        assert result == "contradicted"

    def test_scenario_4_unsafe_confirmed(self):
        """Scenario 4: UNSAFE + AST confirms → confirmed."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[ParameterInfo(name="x", type_hint=None, has_default=False)],
            has_none_checks=[],
        )

        confidence, result = cross_validate_null_safety("UNSAFE", ["x"], facts)

        assert confidence == FindingConfidence.HIGH
        assert result == "confirmed"

    def test_scenario_5_unsafe_contradicted(self):
        """Scenario 5: UNSAFE + AST contradicts (false positive) → contradicted."""
        facts = FunctionFacts(
            function_name="test",
            qualified_name="test",
            line_start=1,
            line_end=2,
            parameters=[ParameterInfo(name="x", type_hint=None, has_default=False)],
            has_none_checks=["x"],  # Has check, but LLM says UNSAFE
        )

        confidence, result = cross_validate_null_safety("UNSAFE", ["x"], facts)

        assert confidence == FindingConfidence.LOW
        assert result == "contradicted"
