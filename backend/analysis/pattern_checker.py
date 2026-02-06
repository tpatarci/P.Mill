"""Tier 2 pattern checks that convert AST facts into verification issues.

Each check is a pure function: FunctionFacts -> Optional[VerificationIssue]
"""

from typing import List, Optional

from backend.models import FindingConfidence, FindingTier, FunctionFacts, VerificationIssue


def check_bare_except(facts: FunctionFacts) -> Optional[VerificationIssue]:
    """
    Check for bare except clause without exception type.

    Formal claim: If has_bare_except is True, the function catches all exceptions
    including SystemExit and KeyboardInterrupt, which is usually unintended.

    Assumptions: AST analysis correctly identified bare except clauses.

    Evidence: AST visitor detected 'except:' without exception type.

    Limitations: Does not distinguish between intentional and unintentional use.
    """
    if not facts.has_bare_except:
        return None

    return VerificationIssue(
        issue_id=f"{facts.qualified_name}:bare_except",
        severity="medium",
        category="maintainability",
        title="Bare except clause without exception type",
        description=(
            f"Function {facts.function_name} uses bare 'except:' which catches "
            f"all exceptions including SystemExit and KeyboardInterrupt. "
            f"This can hide unexpected errors and make debugging difficult."
        ),
        location=f"{facts.function_name}:{facts.line_start}",
        tier=FindingTier.TIER2_HEURISTIC,
        confidence=FindingConfidence.HIGH,
        evidence=[
            f"AST analysis shows bare except clause at line {facts.line_start}",
            "Bare except catches all exceptions, including system-level exceptions"
        ],
        suggested_fix=(
            "Specify the exception type you expect: 'except ValueError:' "
            "or 'except Exception:' for broader but still selective catching"
        )
    )


def check_mutable_defaults(facts: FunctionFacts) -> Optional[VerificationIssue]:
    """
    Check for mutable default arguments.

    Formal claim: If has_mutable_default_args is True, the function has a mutable
    default argument which can lead to unexpected behavior when the default is
    modified across calls.

    Assumptions: AST analysis correctly identified list, dict, or set defaults.

    Evidence: AST visitor detected default values that are list, dict, or set literals.

    Limitations: Does not detect if the mutable default is intentionally used
    (e.g., for memoization).
    """
    if not facts.has_mutable_default_args:
        return None

    mutable_params = [
        p.name for p in facts.parameters if p.default_is_mutable
    ]

    return VerificationIssue(
        issue_id=f"{facts.qualified_name}:mutable_defaults",
        severity="medium",
        category="logic",
        title="Mutable default argument detected",
        description=(
            f"Function {facts.function_name} has mutable default arguments: "
            f"{', '.join(mutable_params)}. Mutable defaults are evaluated once "
            f"at function definition time, not each time the function is called. "
            f"This can lead to unexpected behavior when the default is modified."
        ),
        location=f"{facts.function_name}:{facts.line_start}",
        tier=FindingTier.TIER2_HEURISTIC,
        confidence=FindingConfidence.HIGH,
        evidence=[
            f"Parameters with mutable defaults: {', '.join(mutable_params)}",
            "Mutable defaults (list, dict, set) are shared across all function calls"
        ],
        suggested_fix=(
            "Use None as default and create the mutable object inside the function: "
            "def f(x=None): x = x or []"
        )
    )


def check_resource_leak(facts: FunctionFacts) -> Optional[VerificationIssue]:
    """
    Check for resource leak risk (open() without context manager).

    Formal claim: If uses_open_without_with is True, the function opens files
    without a context manager, which can lead to resource leaks if exceptions
    occur before the file is closed.

    Assumptions: AST analysis correctly identified open() calls not in with statements.

    Evidence: AST visitor detected open() call without surrounding 'with' statement.

    Limitations: May produce false positives if close() is called explicitly,
    or if the function is guaranteed to complete without exceptions.
    """
    if not facts.uses_open_without_with:
        return None

    return VerificationIssue(
        issue_id=f"{facts.qualified_name}:resource_leak",
        severity="medium",
        category="maintainability",
        title="File opened without context manager",
        description=(
            f"Function {facts.function_name} calls open() without using a "
            f"'with' statement. If an exception occurs before the file is "
            f"explicitly closed, the file handle may leak."
        ),
        location=f"{facts.function_name}:{facts.line_start}",
        tier=FindingTier.TIER2_HEURISTIC,
        confidence=FindingConfidence.MEDIUM,
        evidence=[
            "AST analysis detected open() call without context manager",
            "Files without 'with' statement may not be closed on exceptions"
        ],
        suggested_fix=(
            "Use a context manager: 'with open(path) as f: ...' "
            "to ensure the file is properly closed even if exceptions occur."
        ),
        counterexample=(
            "If an exception occurs between open() and close(), "
            "the file remains open until garbage collection."
        )
    )


def check_command_injection(facts: FunctionFacts) -> Optional[VerificationIssue]:
    """
    Check for command injection risk.

    Formal claim: If uses_command_execution is True and command_execution_has_fstring
    is True, the function executes commands with f-string interpolation, which may
    allow command injection if untrusted input reaches the command string.

    Assumptions: AST analysis correctly identified command execution functions
    and f-string arguments.

    Evidence: AST visitor detected os.system/subprocess.call with f-string arguments.

    Limitations: Cannot determine if the interpolated variables are actually
    user-controlled or properly sanitized.
    """
    if not facts.uses_command_execution:
        return None

    if facts.command_execution_has_fstring:
        return VerificationIssue(
            issue_id=f"{facts.qualified_name}:command_injection",
            severity="critical",
            category="security",
            title="Command injection risk via f-string in command execution",
            description=(
                f"Function {facts.function_name} executes shell commands using "
                f"f-string interpolation. If untrusted input reaches the command "
                f"string, attackers can execute arbitrary commands."
            ),
            location=f"{facts.function_name}:{facts.line_start}",
            tier=FindingTier.TIER2_HEURISTIC,
            confidence=FindingConfidence.HIGH,
            evidence=[
                "Command execution detected: " + ", ".join(
                    c for c in facts.calls if "system" in c or "subprocess" in c or "popen" in c
                ),
                "Command arguments include f-string interpolation"
            ],
            suggested_fix=(
                "Use subprocess.run with a list of arguments (shell=False) "
                "or properly validate/escape user input."
            ),
            counterexample='If user_input = "; rm -rf /", then os.system(f"echo {user_input}") executes arbitrary commands.'
        )
    else:
        return VerificationIssue(
            issue_id=f"{facts.qualified_name}:command_execution",
            severity="high",
            category="security",
            title="Command execution detected",
            description=(
                f"Function {facts.function_name} executes shell commands. "
                f"Ensure all inputs are properly validated and sanitized."
            ),
            location=f"{facts.function_name}:{facts.line_start}",
            tier=FindingTier.TIER2_HEURISTIC,
            confidence=FindingConfidence.MEDIUM,
            evidence=[
                "Command execution detected: " + ", ".join(
                    c for c in facts.calls if "system" in c or "subprocess" in c or "popen" in c
                )
            ],
            suggested_fix=(
                "Consider alternatives to shell commands. If necessary, "
                "use subprocess.run with shell=False and argument list."
            )
        )


def check_implicit_none_return(facts: FunctionFacts) -> Optional[VerificationIssue]:
    """
    Check for implicit None return when return annotation exists.

    Formal claim: If return_annotation is not None and has_return_on_all_paths
    is False, the function may implicitly return None on some code paths,
    violating its type annotation.

    Assumptions: AST analysis correctly identified return statements and
    return annotations.

    Evidence: Function has return annotation but may not return on all paths.

    Limitations: Control flow analysis is simplified; may have false positives
    or negatives for complex control flow.
    """
    if not facts.return_annotation:
        return None

    if facts.has_return_on_all_paths:
        return None

    return VerificationIssue(
        issue_id=f"{facts.qualified_name}:implicit_none_return",
        severity="medium",
        category="logic",
        title="Possible implicit None return with type annotation",
        description=(
            f"Function {facts.function_name} has return annotation "
            f"'{facts.return_annotation}' but may not return a value on all "
            f"code paths. Python functions without an explicit return statement "
            f"implicitly return None, which violates the type annotation."
        ),
        location=f"{facts.function_name}:{facts.line_start}",
        tier=FindingTier.TIER2_HEURISTIC,
        confidence=FindingConfidence.MEDIUM,
        evidence=[
            f"Return annotation: {facts.return_annotation}",
            "Control flow analysis suggests not all paths return a value"
        ],
        suggested_fix=(
            "Ensure all code paths return a value, or change return annotation "
            "to 'Optional[{return_type}]' or 'None'."
        )
    )


def check_unreachable_code(facts: FunctionFacts) -> Optional[VerificationIssue]:
    """
    Check for unreachable code after unconditional return/raise.

    Formal claim: If has_unreachable_code is True, the function contains code
    that can never be executed because it follows an unconditional return or raise.

    Assumptions: AST analysis correctly identified unreachable statements.

    Evidence: AST visitor detected statements after unconditional return/raise.

    Limitations: Simplified analysis may miss some unreachable code or produce
    false positives for complex control flow.
    """
    if not facts.has_unreachable_code:
        return None

    return VerificationIssue(
        issue_id=f"{facts.qualified_name}:unreachable_code",
        severity="low",
        category="maintainability",
        title="Unreachable code detected",
        description=(
            f"Function {facts.function_name} contains code that can never be "
            f"executed because it follows an unconditional return or raise "
            f"statement. This is dead code that should be removed."
        ),
        location=f"{facts.function_name}:{facts.line_start}",
        tier=FindingTier.TIER2_HEURISTIC,
        confidence=FindingConfidence.MEDIUM,
        evidence=[
            "AST analysis detected statements after unconditional return/raise"
        ],
        suggested_fix="Remove the unreachable code or adjust control flow."
    )


def check_giant_function(facts: FunctionFacts) -> Optional[VerificationIssue]:
    """
    Check for oversized function (too many lines or too complex).

    Formal claim: If LOC > 50 or cyclomatic_complexity > 10, the function is
    too large and should be refactored for better maintainability.

    Thresholds:
    - LOC > 50 lines
    - Cyclomatic complexity > 10

    Assumptions: These thresholds are appropriate heuristics for function size.

    Evidence: LOC={loc}, complexity={complexity}.

    Limitations: Thresholds are arbitrary; some functions legitimately require
    more lines or complexity.
    """
    LOC_THRESHOLD = 50
    COMPLEXITY_THRESHOLD = 10

    reasons = []
    if facts.loc > LOC_THRESHOLD:
        reasons.append(f"{facts.loc} lines (threshold: {LOC_THRESHOLD})")
    if facts.cyclomatic_complexity > COMPLEXITY_THRESHOLD:
        reasons.append(f"complexity {facts.cyclomatic_complexity} (threshold: {COMPLEXITY_THRESHOLD})")

    if not reasons:
        return None

    return VerificationIssue(
        issue_id=f"{facts.qualified_name}:giant_function",
        severity="medium",
        category="maintainability",
        title="Function exceeds size/complexity thresholds",
        description=(
            f"Function {facts.function_name} exceeds recommended thresholds: "
            f"{', '.join(reasons)}. Large functions are harder to test, debug, and maintain."
        ),
        location=f"{facts.function_name}:{facts.line_start}",
        tier=FindingTier.TIER2_HEURISTIC,
        confidence=FindingConfidence.MEDIUM,
        evidence=[
            f"Lines of code: {facts.loc}",
            f"Cyclomatic complexity: {facts.cyclomatic_complexity}"
        ],
        suggested_fix=(
            "Consider splitting the function into smaller helper functions "
            "or reduce nesting levels."
        )
    )


def check_star_imports(facts: FunctionFacts) -> Optional[VerificationIssue]:
    """
    Check for star imports at module level.

    Formal claim: If star_imports_used is True, the module uses 'from x import *'
    which pollutes the namespace and makes code harder to understand.

    Assumptions: AST analysis correctly identified star imports.

    Evidence: AST visitor detected 'from x import *' statement.

    Limitations: Star imports may be acceptable in __init__.py files or test modules.
    """
    if not facts.star_imports_used:
        return None

    return VerificationIssue(
        issue_id=f"{facts.qualified_name}:star_imports",
        severity="low",
        category="maintainability",
        title="Star import detected",
        description=(
            f"Function {facts.function_name} is in a module that uses star "
            f"imports ('from x import *'). Star imports pollute the namespace, "
            f"make code harder to understand, and can accidentally shadow names."
        ),
        location=f"{facts.function_name}:{facts.line_start}",
        tier=FindingTier.TIER2_HEURISTIC,
        confidence=FindingConfidence.MEDIUM,
        evidence=[
            "AST analysis detected star import statement in module"
        ],
        suggested_fix=(
            "Use explicit imports: 'from module import name1, name2' "
            "or 'import module' and reference with module.name."
        )
    )


def check_broad_exception(facts: FunctionFacts) -> Optional[VerificationIssue]:
    """
    Check for broad exception catching (Exception or BaseException).

    Formal claim: If has_broad_except is True, the function catches Exception
    or BaseException which is overly broad and may hide unexpected errors.

    Assumptions: AST analysis correctly identified broad except clauses.

    Evidence: AST visitor detected 'except Exception:' or 'except BaseException:'.

    Limitations: Broad exception catching may be intentional for top-level error handlers.
    """
    if not facts.has_broad_except:
        return None

    broad_types = [t for t in facts.caught_types if t in ("Exception", "BaseException")]

    return VerificationIssue(
        issue_id=f"{facts.qualified_name}:broad_exception",
        severity="medium",
        category="maintainability",
        title="Broad exception catch detected",
        description=(
            f"Function {facts.function_name} catches broad exception types: "
            f"{', '.join(broad_types)}. This can hide unexpected errors "
            f"and make debugging difficult."
        ),
        location=f"{facts.function_name}:{facts.line_start}",
        tier=FindingTier.TIER2_HEURISTIC,
        confidence=FindingConfidence.HIGH,
        evidence=[
            f"Caught exception types: {', '.join(broad_types)}"
        ],
        suggested_fix=(
            "Catch specific exception types instead: 'except ValueError:' "
            "or 'except (ValueError, TypeError):'. "
            "Use 'except Exception:' only at the top level of a program."
        )
    )


def check_shadow_builtin(facts: FunctionFacts) -> Optional[VerificationIssue]:
    """
    Check for parameter names that shadow Python builtins.

    Formal claim: If shadows_builtin is not empty, the function has parameters
    that shadow Python builtins, which can lead to confusion and bugs.

    Assumptions: AST analysis correctly identified builtin shadowing.

    Evidence: Parameter names match Python builtin names.

    Limitations: Intentional shadowing for compatibility may be acceptable in some cases.
    """
    if not facts.shadows_builtin:
        return None

    return VerificationIssue(
        issue_id=f"{facts.qualified_name}:shadow_builtin",
        severity="low",
        category="maintainability",
        title="Parameter shadows Python builtin",
        description=(
            f"Function {facts.function_name} has parameters that shadow Python "
            f"builtins: {', '.join(facts.shadows_builtin)}. This can lead to "
            f"confusion and bugs when trying to use the builtin later."
        ),
        location=f"{facts.function_name}:{facts.line_start}",
        tier=FindingTier.TIER2_HEURISTIC,
        confidence=FindingConfidence.HIGH,
        evidence=[
            f"Shadowed builtins: {', '.join(facts.shadows_builtin)}"
        ],
        suggested_fix=(
            "Rename parameters to avoid shadowing builtins. "
            "Use a trailing underscore if necessary: 'list_' instead of 'list'."
        )
    )


# All Tier 2 checks - run in sequence
TIER2_CHECKS = [
    check_bare_except,
    check_mutable_defaults,
    check_resource_leak,
    check_command_injection,
    check_implicit_none_return,
    check_unreachable_code,
    check_giant_function,
    check_star_imports,
    check_broad_exception,
    check_shadow_builtin,
]


def run_tier2_checks(facts: FunctionFacts) -> List[VerificationIssue]:
    """
    Run all Tier 2 pattern checks on a function.

    Args:
        facts: Extracted function facts from AST analysis

    Returns:
        List of VerificationIssue objects (one for each check that found an issue)
    """
    issues = []
    for check in TIER2_CHECKS:
        try:
            issue = check(facts)
            if issue:
                issues.append(issue)
        except Exception as e:
            # Individual check failures should not stop the entire pipeline
            import structlog
            logger = structlog.get_logger()
            logger.warning(
                "tier2_check_failed",
                check=check.__name__,
                function=facts.function_name,
                error=str(e)
            )
    return issues
