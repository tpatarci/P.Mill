"""LLM-based contract inference for Python code.

This module uses LLMs to infer implicit contracts:
- Preconditions not explicitly documented
- Postconditions from code behavior
- Implicit assumptions about inputs
- Guaranteed behaviors
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog

from backend.analysis.contracts import Contract
from backend.llm.adapter import LLMAdapter, StubLLMAdapter

logger = structlog.get_logger()


# Contract inference prompts
CONTRACT_INFERENCE_PROMPT = """You are analyzing Python code to infer implicit contracts.

Given the following Python function:

```python
{function_code}
```

Analyze the function and provide:
1. Preconditions: What must be true about inputs for the function to work correctly?
2. Postconditions: What does the function guarantee about its outputs/side effects?
3. Assumptions: What implicit assumptions does the code make?
4. Raises: What exceptions might be raised and under what conditions?

Respond in JSON format:
{{
    "preconditions": ["condition1", "condition2"],
    "postconditions": ["guarantee1", "guarantee2"],
    "assumptions": ["assumption1"],
    "raises": ["ExceptionType: condition"]
}}

Only include conditions that are explicitly checked or implied by the code logic."""


INVARIANT_INFERENCE_PROMPT = """You are analyzing a Python class to infer invariants.

Given the following Python class:

```python
{class_code}
```

Identify class invariants - conditions that must always be true for instances of this class.

Look for:
1. Validation in __init__
2. Assertions throughout methods
3. Property constraints
4. State consistency requirements

Respond in JSON format:
{{
    "invariants": ["invariant1", "invariant2"],
    "state_constraints": ["constraint1"]
}}"""


@dataclass
class InferredContract:
    """A contract inferred by LLM analysis."""

    function_name: str
    preconditions: List[str]
    postconditions: List[str]
    assumptions: List[str]
    raises: List[str]
    confidence: str  # "low", "medium", "high"
    raw_response: Optional[str] = None


@dataclass
class InferredInvariant:
    """An invariant inferred by LLM analysis."""

    class_name: str
    invariants: List[str]
    state_constraints: List[str]
    confidence: str
    raw_response: Optional[str] = None


class ContractInference:
    """Infer contracts using LLM analysis."""

    def __init__(self, llm_adapter: Optional[LLMAdapter] = None):
        self.llm_adapter = llm_adapter
        if llm_adapter is None:
            # Use stub for testing/fallback
            self.llm_adapter = StubLLMAdapter({
                "contract_inference": '{"preconditions": [], "postconditions": [], "assumptions": [], "raises": []}',
            })

    async def infer_function_contract(
        self,
        function_code: str,
        function_name: str,
    ) -> InferredContract:
        """
        Infer contract for a function using LLM.

        Args:
            function_code: Source code of the function
            function_name: Name of the function

        Returns:
            InferredContract with inferred conditions
        """
        prompt = CONTRACT_INFERENCE_PROMPT.format(function_code=function_code)

        try:
            response = await self.llm_adapter.complete(prompt)

            # Parse JSON response
            import json
            try:
                data = json.loads(response)
                preconditions = data.get("preconditions", [])
                postconditions = data.get("postconditions", [])
                assumptions = data.get("assumptions", [])
                raises = data.get("raises", [])
                confidence = self._estimate_confidence(function_code, data)
            except json.JSONDecodeError:
                # Fallback to empty contract on parse error
                preconditions = []
                postconditions = []
                assumptions = []
                raises = []
                confidence = "low"

            return InferredContract(
                function_name=function_name,
                preconditions=preconditions,
                postconditions=postconditions,
                assumptions=assumptions,
                raises=raises,
                confidence=confidence,
                raw_response=response,
            )

        except Exception as e:
            logger.warning("llm_contract_inference_failed", function=function_name, error=str(e))
            return InferredContract(
                function_name=function_name,
                preconditions=[],
                postconditions=[],
                assumptions=[],
                raises=[],
                confidence="low",
            )

    async def infer_class_invariants(
        self,
        class_code: str,
        class_name: str,
    ) -> InferredInvariant:
        """
        Infer invariants for a class using LLM.

        Args:
            class_code: Source code of the class
            class_name: Name of the class

        Returns:
            InferredInvariant with inferred invariants
        """
        prompt = INVARIANT_INFERENCE_PROMPT.format(class_code=class_code)

        try:
            response = await self.llm_adapter.complete(prompt)

            import json
            try:
                data = json.loads(response)
                invariants = data.get("invariants", [])
                state_constraints = data.get("state_constraints", [])
                confidence = self._estimate_class_confidence(class_code, data)
            except json.JSONDecodeError:
                invariants = []
                state_constraints = []
                confidence = "low"

            return InferredInvariant(
                class_name=class_name,
                invariants=invariants,
                state_constraints=state_constraints,
                confidence=confidence,
                raw_response=response,
            )

        except Exception as e:
            logger.warning("llm_invariant_inference_failed", class_name=class_name, error=str(e))
            return InferredInvariant(
                class_name=class_name,
                invariants=[],
                state_constraints=[],
                confidence="low",
            )

    def _estimate_confidence(self, function_code: str, inferred_data: Dict) -> str:
        """Estimate confidence in inferred contract based on code clarity."""
        # Simple heuristic based on code length and specificity
        lines = function_code.split("\n")
        code_length = len(lines)

        # More specific conditions = higher confidence
        total_items = (
            len(inferred_data.get("preconditions", [])) +
            len(inferred_data.get("postconditions", [])) +
            len(inferred_data.get("assumptions", [])) +
            len(inferred_data.get("raises", []))
        )

        if total_items >= 4 and code_length < 30:
            return "high"
        elif total_items >= 2 and code_length < 50:
            return "medium"
        else:
            return "low"

    def _estimate_class_confidence(self, class_code: str, inferred_data: Dict) -> str:
        """Estimate confidence in inferred invariants."""
        total_items = (
            len(inferred_data.get("invariants", [])) +
            len(inferred_data.get("state_constraints", []))
        )

        if total_items >= 3:
            return "high"
        elif total_items >= 1:
            return "medium"
        else:
            return "low"


class StaticContractInference:
    """Infer contracts statically without LLM (fallback)."""

    @staticmethod
    def infer_from_function_source(source_code: str, function_name: str) -> InferredContract:
        """
        Infer contract from function source using static analysis.

        Args:
            source_code: Full source code containing the function
            function_name: Name of the function to analyze

        Returns:
            InferredContract with inferred conditions
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return InferredContract(
                function_name=function_name,
                preconditions=[],
                postconditions=[],
                assumptions=[],
                raises=[],
                confidence="low",
            )

        # Find the function node
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
                func_node = node
                break

        if not func_node:
            return InferredContract(
                function_name=function_name,
                preconditions=[],
                postconditions=[],
                assumptions=[],
                raises=[],
                confidence="low",
            )

        preconditions = []
        postconditions = []
        raises = []
        assumptions = []

        # Analyze function body
        for node in ast.walk(func_node):
            # Detect precondition-like patterns
            if isinstance(node, ast.Assert):
                condition = ast.unparse(node.test)
                if isinstance(node, ast.Assert) and hasattr(node, 'lineno'):
                    # Check if assert is early in function
                    relative_pos = node.lineno - func_node.lineno
                    if relative_pos <= 5:  # First few lines = likely precondition
                        preconditions.append(condition)

            # Detect raise statements
            if isinstance(node, ast.Raise):
                if node.exc:
                    if isinstance(node.exc, ast.Call):
                        if isinstance(node.exc.func, ast.Name):
                            exc_name = node.exc.func.id
                            raises.append(f"{exc_name}: raised based on condition")

        # Infer from type hints
        for arg in func_node.args.args:
            if arg.annotation:
                annotation = ast.unparse(arg.annotation)
                if "Optional" in annotation or "None" in annotation:
                    assumptions.append(f"{arg.arg} may be None")
                elif "int" in annotation:
                    assumptions.append(f"{arg.arg} should be an integer")
                elif "str" in annotation:
                    assumptions.append(f"{arg.arg} should be a string")

        # Infer from return type
        if func_node.returns:
            return_type = ast.unparse(func_node.returns)
            if "bool" in return_type:
                postconditions.append("returns a boolean value")

        return InferredContract(
            function_name=function_name,
            preconditions=preconditions,
            postconditions=postconditions,
            assumptions=assumptions,
            raises=raises,
            confidence="medium",
        )

    @staticmethod
    def infer_class_invariants(source_code: str, class_name: str) -> InferredInvariant:
        """
        Infer invariants for a class using static analysis.

        Args:
            source_code: Full source code
            class_name: Name of the class

        Returns:
            InferredInvariant with inferred invariants
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return InferredInvariant(
                class_name=class_name,
                invariants=[],
                state_constraints=[],
                confidence="low",
            )

        # Find the class node
        class_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                class_node = node
                break

        if not class_node:
            return InferredInvariant(
                class_name=class_name,
                invariants=[],
                state_constraints=[],
                confidence="low",
            )

        invariants = []
        state_constraints = []

        # Look for __init__ validation
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                # Check for assert statements in __init__
                for node in ast.walk(item):
                    if isinstance(node, ast.Assert):
                        condition = ast.unparse(node.test)
                        if "self." in condition:
                            invariants.append(condition)

        return InferredInvariant(
            class_name=class_name,
            invariants=invariants,
            state_constraints=state_constraints,
            confidence="low",
        )


def merge_contracts(
    explicit: Contract,
    inferred: InferredContract,
) -> Contract:
    """
    Merge explicit and inferred contracts.

    Args:
        explicit: Explicitly documented contract
        inferred: LLM-inferred contract

    Returns:
        Merged Contract with both sources
    """
    return Contract(
        function_name=explicit.function_name,
        preconditions=list(set(explicit.preconditions + inferred.preconditions)),
        postconditions=list(set(explicit.postconditions + inferred.postconditions)),
        invariants=list(set(explicit.invariants)),
        raises=list(set(explicit.raises + inferred.raises)),
        raises_in_code=explicit.raises_in_code,
        requires_types=explicit.requires_types,
        return_type=explicit.return_type,
        assumptions=list(set(explicit.assumptions + inferred.assumptions)),
        guarantees=list(set(explicit.guarantees + inferred.postconditions)),
    )
