"""Contract extraction from Python code.

This module extracts formal contracts from:
- Docstrings (preconditions, postconditions, invariants)
- Assert statements
- Type hints
- Raise statements
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

from backend.models import FunctionInfo

logger = structlog.get_logger()


@dataclass
class Contract:
    """A formal contract for a function."""

    function_name: str
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    invariants: List[str] = field(default_factory=list)
    raises: List[str] = field(default_factory=list)  # Documented raises from docstring
    raises_in_code: List[str] = field(default_factory=list)  # Actually raised in code
    requires_types: Dict[str, str] = field(default_factory=dict)
    return_type: Optional[str] = None
    assumptions: List[str] = field(default_factory=list)
    guarantees: List[str] = field(default_factory=list)


@dataclass
class ContractViolation:
    """A detected contract violation."""

    violation_type: str  # "inconsistent_contract", "missing precondition", etc.
    function_name: str
    location: str  # file:line
    severity: str  # "low", "medium", "high", "critical"
    description: str
    suggestion: Optional[str] = None


class ContractExtractor(ast.NodeVisitor):
    """Extract contracts from Python AST."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.contracts: Dict[str, Contract] = {}
        self.violations: List[ContractViolation] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract contract from function definition."""
        contract = Contract(function_name=node.name)

        # Extract return type
        if node.returns:
            contract.return_type = ast.unparse(node.returns)

        # Extract parameter type hints
        for arg in node.args.args:
            if arg.annotation:
                param_name = arg.arg
                param_type = ast.unparse(arg.annotation)
                contract.requires_types[param_name] = param_type

        # Extract from docstring
        docstring = ast.get_docstring(node)
        if docstring:
            self._extract_from_docstring(docstring, contract)

        # Extract from assert statements (preconditions)
        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                condition = ast.unparse(child.test)
                # Asserts at function start are preconditions
                if isinstance(child, ast.Assert) and hasattr(child, 'lineno'):
                    contract.preconditions.append(condition)

        # Extract from raise statements (store separately from documented raises)
        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                if child.exc:
                    exc_type = self._get_exception_type(child.exc)
                    if exc_type:
                        contract.raises_in_code.append(exc_type)

        # Store contract
        self.contracts[node.name] = contract

        # Validate contract consistency
        self._validate_contract(node, contract)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Extract contract from async function definition."""
        self.visit_FunctionDef(node)

    def _extract_from_docstring(self, docstring: str, contract: Contract) -> None:
        """Extract contract information from docstring."""
        lines = docstring.split("\n")

        # Look for common contract patterns in docstrings
        # Google style: Args:, Returns:, Raises:, Preconditions:, Postconditions:
        # Sphinx style: :param:, :type:, :returns:, :raises:, :precondition:, :postcondition:
        # Numpy style: Parameters, Returns, Raises, Other Parameters

        in_args_section = False
        in_returns_section = False
        in_raises_section = False
        in_precondition_section = False
        in_postcondition_section = False

        for line in lines:
            line = line.strip()

            # Google style sections
            if line.startswith("Args:") or line.startswith("Arguments:"):
                in_args_section = True
                in_returns_section = False
                in_raises_section = False
                in_precondition_section = False
                in_postcondition_section = False
            elif line.startswith("Returns:"):
                in_returns_section = True
                in_args_section = False
                in_raises_section = False
                in_precondition_section = False
                in_postcondition_section = False
            elif line.startswith("Raises:"):
                in_raises_section = True
                in_args_section = False
                in_returns_section = False
                in_precondition_section = False
                in_postcondition_section = False
            elif line.startswith("Precondition:") or line.startswith("Preconditions:"):
                in_precondition_section = True
                in_args_section = False
                in_returns_section = False
                in_raises_section = False
                in_postcondition_section = False
            elif line.startswith("Postcondition:") or line.startswith("Postconditions:"):
                in_postcondition_section = True
                in_args_section = False
                in_returns_section = False
                in_raises_section = False
                in_precondition_section = False
            elif line and not line[0].islower() and ":" in line:
                # New section
                in_args_section = False
                in_returns_section = False
                in_raises_section = False
                in_precondition_section = False
                in_postcondition_section = False

            # Extract based on section
            if in_precondition_section and line and not line.startswith("Precondition"):
                contract.preconditions.append(line)
                contract.assumptions.append(line)
            elif in_postcondition_section and line and not line.startswith("Postcondition"):
                contract.postconditions.append(line)
                contract.guarantees.append(line)
            elif in_raises_section and line and not line.startswith("Raises"):
                # Extract exception type
                match = re.match(r'(\w+):', line)
                if match:
                    contract.raises.append(match.group(1))
                else:
                    # Take first word as exception type
                    parts = line.split(None, 1)
                    if parts:
                        contract.raises.append(parts[0])

        # Also look for :param: / :type: / :returns: / :raises: patterns (Sphinx)
        for line in lines:
            if ":precondition:" in line.lower():
                # Extract precondition
                match = re.search(r':precondition:\s*(.+)', line, re.IGNORECASE)
                if match:
                    contract.preconditions.append(match.group(1).strip())
            elif ":postcondition:" in line.lower():
                match = re.search(r':postcondition:\s*(.+)', line, re.IGNORECASE)
                if match:
                    contract.postconditions.append(match.group(1).strip())
            elif ":raises:" in line.lower():
                match = re.search(r':raises:\s*(\w+)', line, re.IGNORECASE)
                if match:
                    contract.raises.append(match.group(1))
            elif ":requires:" in line.lower():
                match = re.search(r':requires:\s*(.+)', line, re.IGNORECASE)
                if match:
                    contract.preconditions.append(match.group(1).strip())
            elif ":ensures:" in line.lower():
                match = re.search(r':ensures:\s*(.+)', line, re.IGNORECASE)
                if match:
                    contract.postconditions.append(match.group(1).strip())

    def _get_exception_type(self, node: ast.AST) -> Optional[str]:
        """Get exception type from raise statement."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            return ast.unparse(node.func)
        return None

    def _validate_contract(self, node: ast.FunctionDef, contract: Contract) -> None:
        """Validate contract for consistency."""
        # Check for undocumented raises
        documented = set(contract.raises)
        in_code = set(contract.raises_in_code)

        # Skip generic exceptions
        generic_exceptions = {"Exception", "BaseException"}
        code_specific = in_code - generic_exceptions

        # Check for exceptions raised but not documented
        undocumented = code_specific - documented
        for exc in undocumented:
            self.violations.append(
                ContractViolation(
                    violation_type="undocumented_raise",
                    function_name=node.name,
                    location=f"{node.name}:{node.lineno}",
                    severity="low",
                    description=f"Function raises {exc} but not documented in Raises: section",
                    suggestion=f"Add {exc} to the Raises: section of docstring",
                )
            )

        # Check for documented exceptions not actually raised
        documented_not_raised = documented - in_code
        for exc in documented_not_raised:
            self.violations.append(
                ContractViolation(
                    violation_type="unreachable_raise",
                    function_name=node.name,
                    location=f"{node.name}:{node.lineno}",
                    severity="low",
                    description=f"Function documents {exc} in Raises: but never raises it",
                    suggestion=f"Remove {exc} from Raises: section or add code that raises it",
                )
            )


def extract_contracts(source_code: str) -> Dict[str, Contract]:
    """
    Extract all contracts from source code.

    Args:
        source_code: Python source code

    Returns:
        Dict mapping function names to Contract objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {}

    extractor = ContractExtractor(source_code)
    extractor.visit(tree)

    return extractor.contracts


def extract_function_contract(
    source_code: str,
    function_name: str,
) -> Optional[Contract]:
    """
    Extract contract for a specific function.

    Args:
        source_code: Python source code
        function_name: Name of function to extract contract from

    Returns:
        Contract object or None if function not found
    """
    contracts = extract_contracts(source_code)
    return contracts.get(function_name)


def validate_contracts(
    source_code: str,
    functions: List[FunctionInfo],
) -> List[ContractViolation]:
    """
    Validate all contracts in source code.

    Args:
        source_code: Python source code
        functions: List of functions to validate

    Returns:
        List of ContractViolation objects
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    extractor = ContractExtractor(source_code)
    extractor.visit(tree)

    violations = []

    # Check for missing documentation on functions with complex logic
    for func in functions:
        if func.name in extractor.contracts:
            contract = extractor.contracts[func.name]
            # Check if complex function lacks proper documentation
            func_node = None
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func.name:
                    func_node = node
                    break

            if func_node:
                # Check for complexity (number of branches)
                branch_count = sum(1 for _ in ast.walk(func_node) if isinstance(_, (ast.If, ast.For, ast.While, ast.Try)))

                if branch_count > 3 and not contract.preconditions and not contract.postconditions:
                    violations.append(
                        ContractViolation(
                            violation_type="missing_contract",
                            function_name=func.name,
                            location=f"{func.name}:{func.line_start}",
                            severity="medium",
                            description=f"Complex function ({branch_count} branches) lacks documented contracts",
                            suggestion="Add preconditions and postconditions to document expected behavior",
                        )
                    )

                # Check for functions with asserts but no preconditions documented
                has_asserts = any(isinstance(child, ast.Assert) for child in ast.walk(func_node))
                if has_asserts and not contract.preconditions:
                    violations.append(
                        ContractViolation(
                            violation_type="undocumented_precondition",
                            function_name=func.name,
                            location=f"{func.name}:{func.line_start}",
                            severity="low",
                            description="Function has assert statements but no documented preconditions",
                            suggestion="Document preconditions in the docstring (e.g., Preconditions:)",
                        )
                    )

        # Check for functions that raise but no Raises section
        if func.name in extractor.contracts:
            contract = extractor.contracts[func.name]
            func_node = None
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func.name:
                    func_node = node
                    break

            if func_node:
                raises_in_code = set()
                for child in ast.walk(func_node):
                    if isinstance(child, ast.Raise) and child.exc:
                        exc_type = extractor._get_exception_type(child.exc)
                        if exc_type:
                            raises_in_code.add(exc_type)

                # If specific exceptions are raised but not documented
                documented_raises = set(contract.raises)
                code_raises = raises_in_code - {"Exception", "BaseException"}  # Exclude generic
                undocumented = code_raises - documented_raises

                if undocumented:
                    for exc in undocumented:
                        violations.append(
                            ContractViolation(
                                violation_type="undocumented_raise",
                                function_name=func.name,
                                location=f"{func.name}:{func.line_start}",
                                severity="low",
                                description=f"Raises {exc} but not documented",
                                suggestion=f"Add {exc} to the Raises: section",
                            )
                        )

    violations.extend(extractor.violations)
    return violations


def generate_contract_report(
    contracts: Dict[str, Contract],
    violations: List[ContractViolation],
) -> dict:
    """
    Generate a comprehensive contract analysis report.

    Args:
        contracts: Dict of function contracts
        violations: List of contract violations

    Returns:
        Dict with summary and details
    """
    # Count functions with contracts
    total_contracts = len(contracts)
    with_preconditions = sum(1 for c in contracts.values() if c.preconditions)
    with_postconditions = sum(1 for c in contracts.values() if c.postconditions)
    with_raises = sum(1 for c in contracts.values() if c.raises)
    with_type_hints = sum(1 for c in contracts.values() if c.requires_types)

    # Count violations by severity
    severity_counts: Dict[str, int] = {}
    for v in violations:
        severity_counts[v.severity] = severity_counts.get(v.severity, 0) + 1

    # Count violations by type
    type_counts: Dict[str, int] = {}
    for v in violations:
        type_counts[v.violation_type] = type_counts.get(v.violation_type, 0) + 1

    return {
        "summary": {
            "total_functions_analyzed": total_contracts,
            "functions_with_preconditions": with_preconditions,
            "functions_with_postconditions": with_postconditions,
            "functions_with_raises_documented": with_raises,
            "functions_with_type_hints": with_type_hints,
            "total_violations": len(violations),
            "violations_by_severity": severity_counts,
            "violations_by_type": type_counts,
        },
        "contracts": [
            {
                "function": name,
                "preconditions": c.preconditions,
                "postconditions": c.postconditions,
                "raises": c.raises,
                "parameter_types": c.requires_types,
                "return_type": c.return_type,
            }
            for name, c in contracts.items()
        ],
        "violations": [
            {
                "type": v.violation_type,
                "function": v.function_name,
                "location": v.location,
                "severity": v.severity,
                "description": v.description,
                "suggestion": v.suggestion,
            }
            for v in violations
        ],
    }


class AssertAnalyzer(ast.NodeVisitor):
    """Analyze assert statements for contract-like properties."""

    def __init__(self) -> None:
        self.preconditions: List[Tuple[str, int]] = []  # (condition, line)
        self.invariants: List[Tuple[str, int]] = []
        self.postconditions: List[Tuple[str, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Analyze asserts in function."""
        body = node.body

        # Asserts at start are preconditions
        for i, stmt in enumerate(body[:5]):  # Check first 5 statements
            if isinstance(stmt, ast.Assert):
                condition = ast.unparse(stmt.test)
                self.preconditions.append((condition, stmt.lineno))
            else:
                break  # Stop if non-assert found

        # Asserts at end (before return) could be postconditions
        for stmt in reversed(body[-5:]):  # Check last 5 statements
            if isinstance(stmt, ast.Assert):
                condition = ast.unparse(stmt.test)
                self.postconditions.append((condition, stmt.lineno))
            elif isinstance(stmt, ast.Return):
                continue
            else:
                break

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Look for invariant-like asserts in __init__."""
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                for stmt in item.body:
                    if isinstance(stmt, ast.Assert):
                        condition = ast.unparse(stmt.test)
                        if "self." in condition:
                            self.invariants.append((condition, stmt.lineno))


def analyze_assert_contracts(source_code: str) -> Dict[str, List[Tuple[str, int]]]:
    """
    Analyze assert statements to extract implicit contracts.

    Args:
        source_code: Python source code

    Returns:
        Dict with 'preconditions', 'postconditions', 'invariants' keys
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {"preconditions": [], "postconditions": [], "invariants": []}

    analyzer = AssertAnalyzer()
    analyzer.visit(tree)

    return {
        "preconditions": analyzer.preconditions,
        "postconditions": analyzer.postconditions,
        "invariants": analyzer.invariants,
    }
