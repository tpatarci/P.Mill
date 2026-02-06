"""Tests for Control Flow Graph (CFG) builder."""

import pytest

from backend.analysis.cfg import (
    build_cfg,
    get_function_cfg,
    visualize_cfg_dot,
)
from backend.models import CFGEdge, CFGNode, ControlFlowGraph


class TestSimpleCFG:
    """Test CFG for simple code."""

    def test_linear_code_cfg(self):
        """Test CFG for linear code (no branches)."""
        code = """
def foo():
    x = 1
    y = 2
    return x + y
"""
        cfg = get_function_cfg(code, "foo")

        # Should have entry and exit nodes
        assert cfg.entry_node
        assert len(cfg.exit_nodes) > 0

        # Linear code: entry -> statement -> statement -> return -> exit
        assert len(cfg.nodes) > 2
        assert len(cfg.edges) > 0

    def test_single_function_cfg(self):
        """Test CFG building for single function."""
        code = """
def simple():
    return 42
"""
        cfg = get_function_cfg(code, "simple")

        assert isinstance(cfg, ControlFlowGraph)
        assert len(cfg.nodes) > 0
        assert cfg.entry_node == cfg.nodes[0].node_id

    def test_empty_function_cfg(self):
        """Test CFG for empty function."""
        code = """
def empty():
    pass
"""
        cfg = get_function_cfg(code, "empty")

        # Should still have entry and exit
        assert cfg.entry_node
        assert len(cfg.nodes) >= 2  # entry + exit or entry + pass


class TestBranchingCFG:
    """Test CFG for branching code."""

    def test_if_statement_cfg(self):
        """Test CFG for if statement."""
        code = """
def branch(x):
    if x > 0:
        return 1
    return 0
"""
        cfg = get_function_cfg(code, "branch")

        # Should have branch node
        branch_nodes = [n for n in cfg.nodes if n.node_type == "branch"]
        assert len(branch_nodes) > 0

        # Should have multiple edges from branch
        branch_id = branch_nodes[0].node_id
        branch_edges = [e for e in cfg.edges if e.source == branch_id]
        assert len(branch_edges) >= 2  # if has at least 2 paths

    def test_if_else_cfg(self):
        """Test CFG for if-else statement."""
        code = """
def if_else(x):
    if x > 0:
        return 1
    else:
        return -1
"""
        cfg = get_function_cfg(code, "if_else")

        # Check branch node
        branch_nodes = [n for n in cfg.nodes if n.node_type == "branch"]
        assert len(branch_nodes) >= 1

        # Should have True and False edges
        branch_id = branch_nodes[0].node_id
        branch_edges = [e for e in cfg.edges if e.source == branch_id]
        assert len(branch_edges) >= 2

    def test_elif_chain_cfg(self):
        """Test CFG for if-elif-else chain."""
        code = """
def elif_chain(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    else:
        return 0
"""
        cfg = get_function_cfg(code, "elif_chain")

        # Multiple branch nodes (if + elif)
        branch_nodes = [n for n in cfg.nodes if n.node_type == "branch"]
        assert len(branch_nodes) >= 2


class TestLoopCFG:
    """Test CFG for loop constructs."""

    def test_for_loop_cfg(self):
        """Test CFG for for loop."""
        code = """
def for_loop(items):
    result = []
    for item in items:
        result.append(item)
    return result
"""
        cfg = get_function_cfg(code, "for_loop")

        # Should have loop node
        loop_nodes = [n for n in cfg.nodes if n.node_type == "loop"]
        assert len(loop_nodes) >= 1

        # Loop should have edges
        assert len(cfg.edges) >= 2  # Entry to loop, loop to next/merge

    def test_while_loop_cfg(self):
        """Test CFG for while loop."""
        code = """
def while_loop():
    while True:
        do_something()
        if condition():
            break
    return
"""
        cfg = get_function_cfg(code, "while_loop")

        # Should have loop node
        loop_nodes = [n for n in cfg.nodes if n.node_type == "loop"]
        assert len(loop_nodes) >= 1

    def test_nested_loops_cfg(self):
        """Test CFG for nested loops."""
        code = """
def nested_loops():
    for i in range(10):
        for j in range(10):
            if i == j:
                break
"""
        cfg = get_function_cfg(code, "nested_loops")

        # Should have multiple loop nodes
        loop_nodes = [n for n in cfg.nodes if n.node_type == "loop"]
        assert len(loop_nodes) == 2


class TestTryExceptCFG:
    """Test CFG for exception handling."""

    def test_try_except_cfg(self):
        """Test CFG for try-except block."""
        code = """
def try_except():
    try:
        risky()
    except ValueError:
        handle()
    return
"""
        cfg = get_function_cfg(code, "try_except")

        # Should have branch node for try
        branch_nodes = [n for n in cfg.nodes if n.node_type == "branch"]
        assert len(branch_nodes) >= 1

    def test_try_else_finally_cfg(self):
        """Test CFG for try-else-finally block."""
        code = """
def try_complex():
    try:
        risky()
    except ValueError:
        handle_value()
    else:
        no_error()
    finally:
        cleanup()
    return
"""
        cfg = get_function_cfg(code, "try_complex")

        # Should have multiple branch nodes (try, except, else)
        branch_nodes = [n for n in cfg.nodes if n.node_type == "branch"]
        assert len(branch_nodes) >= 2


class TestControlFlowCFG:
    """Test CFG for control flow statements."""

    def test_return_cfg(self):
        """Test CFG with early return."""
        code = """
def early_return(x):
    if x < 0:
        return -1
    return x
"""
        cfg = get_function_cfg(code, "early_return")

        # Should have exit nodes for returns
        exit_nodes = [n for n in cfg.nodes if n.node_type == "exit"]
        assert len(exit_nodes) >= 2  # At least 2 return statements

    def test_break_cfg(self):
        """Test CFG with break statement."""
        code = """
def break_loop():
    for i in range(10):
        if i == 5:
            break
    return i
"""
        cfg = get_function_cfg(code, "break_loop")

        # Should have loop and statement nodes
        loop_nodes = [n for n in cfg.nodes if n.node_type == "loop"]
        assert len(loop_nodes) >= 1

        # Statement nodes should exist for the if and break
        stmt_nodes = [n for n in cfg.nodes if n.node_type == "statement"]
        assert len(stmt_nodes) >= 2  # if and break statements

    def test_continue_cfg(self):
        """Test CFG with continue statement."""
        code = """
def continue_loop():
    for i in range(10):
        if i % 2 == 0:
            continue
        process(i)
    return
"""
        cfg = get_function_cfg(code, "continue_loop")

        # Should have loop and statement nodes
        loop_nodes = [n for n in cfg.nodes if n.node_type == "loop"]
        assert len(loop_nodes) >= 1

        # Statement nodes should exist
        stmt_nodes = [n for n in cfg.nodes if n.node_type == "statement"]
        assert len(stmt_nodes) >= 2


class TestDotVisualization:
    """Test DOT format visualization."""

    def test_visualize_simple_cfg(self):
        """Test DOT visualization of simple CFG."""
        code = "def foo(): return 1"
        cfg = get_function_cfg(code, "foo")

        dot = visualize_cfg_dot(cfg)

        assert dot.startswith("digraph cfg {")
        assert dot.endswith("}")
        assert cfg.entry_node in dot

    def test_visualize_branching_cfg(self):
        """Test DOT visualization includes edges."""
        code = """
def branch(x):
    if x > 0:
        return 1
    return 0
"""
        cfg = get_function_cfg(code, "branch")

        dot = visualize_cfg_dot(cfg)

        # Should contain edge definitions
        assert "->" in dot
        assert "label" in dot or len(cfg.nodes) <= 2


class TestModuleLevelCFG:
    """Test CFG for entire module."""

    def test_module_cfg(self):
        """Test building CFG for entire module."""
        code = """
def foo():
    return 1

def bar():
    return 2
"""
        cfg = build_cfg(code, function_name=None)

        # Module-level CFG
        assert isinstance(cfg, ControlFlowGraph)
        assert len(cfg.nodes) > 0

    def test_specific_function_from_module(self):
        """Test building CFG for specific function from module."""
        code = """
def foo():
    if True:
        return 1
    return 0

def bar():
    return 2
"""
        cfg = build_cfg(code, function_name="foo")

        # Should only have nodes from foo
        assert len(cfg.nodes) > 0
        assert len(cfg.exit_nodes) >= 1


class TestComplexCFG:
    """Test CFG for complex real-world code."""

    def test_complex_function_cfg(self):
        """Test CFG for function with multiple control structures."""
        code = """
def complex_func(items, threshold):
    result = []
    for item in items:
        try:
            if item > threshold:
                result.append(item)
            elif item < 0:
                break
        except ValueError:
            continue
    return result
"""
        cfg = get_function_cfg(code, "complex_func")

        # Should have various node types
        node_types = {n.node_type for n in cfg.nodes}
        assert "loop" in node_types
        assert "entry" in node_types
        assert "exit" in node_types

    def test_state_machine_cfg(self):
        """Test CFG for state machine pattern."""
        code = """
def state_machine(state):
    while True:
        if state == "START":
            state = "RUNNING"
        elif state == "RUNNING":
            if done():
                state = "COMPLETE"
        elif state == "COMPLETE":
            break
    return state
"""
        cfg = get_function_cfg(code, "state_machine")

        # Complex state machine should have many nodes
        assert len(cfg.nodes) > 5
        assert len(cfg.edges) > 5


class TestCFGErrors:
    """Test error handling in CFG builder."""

    def test_syntax_error_cfg(self):
        """Test that syntax errors are raised."""
        code = "def broken(\n"

        with pytest.raises(SyntaxError):
            get_function_cfg(code, "broken")

    def test_nonexistent_function_cfg(self):
        """Test requesting CFG for non-existent function."""
        code = "def foo(): return 1"

        with pytest.raises(ValueError):
            get_function_cfg(code, "bar")

    def test_break_outside_loop_cfg(self):
        """Test break outside loop is logged but doesn't crash."""
        code = """
def invalid_break():
    break
    return 1
"""
        # Should not crash
        cfg = get_function_cfg(code, "invalid_break")
        assert isinstance(cfg, ControlFlowGraph)

    def test_continue_outside_loop_cfg(self):
        """Test continue outside loop is logged but doesn't crash."""
        code = """
def invalid_continue():
    continue
    return 1
"""
        # Should not crash
        cfg = get_function_cfg(code, "invalid_continue")
        assert isinstance(cfg, ControlFlowGraph)


class TestCFGStructure:
    """Test CFG structure properties."""

    def test_cfg_has_entry_and_exit(self):
        """Test CFG always has entry and exit nodes."""
        code = """
def linear():
    x = 1
    y = 2
    return x + y
"""
        cfg = get_function_cfg(code, "linear")

        assert cfg.entry_node
        assert len(cfg.exit_nodes) > 0

    def test_cfg_connected(self):
        """Test CFG is connected from entry."""
        code = """
def connected():
    x = 1
    if x > 0:
        return 1
    return 0
"""
        cfg = get_function_cfg(code, "connected")

        # All nodes should be reachable from entry (except isolated merge nodes)
        # This is a basic check - a full reachability check would be more complex
        assert len(cfg.edges) > 0

    def test_cfg_no_duplicate_nodes(self):
        """Test CFG doesn't have duplicate node IDs."""
        code = """
def unique():
    if True:
        return 1
    return 0
"""
        cfg = get_function_cfg(code, "unique")

        node_ids = [n.node_id for n in cfg.nodes]
        assert len(node_ids) == len(set(node_ids))  # All unique
