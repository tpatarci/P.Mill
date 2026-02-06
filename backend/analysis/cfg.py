"""Control Flow Graph (CFG) builder for Python code."""

import ast
from typing import Dict, List, Optional

import structlog

from backend.models import CFGEdge, CFGNode, ControlFlowGraph

logger = structlog.get_logger()


class CFGBuilder(ast.NodeVisitor):
    """Build control flow graph from Python AST."""

    def __init__(self, source_code: str):
        """Initialize CFG builder.

        Args:
            source_code: Python source code
        """
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.nodes: List[CFGNode] = []
        self.edges: List[CFGEdge] = []
        self.node_counter = 0
        self.entry_node: Optional[str] = None
        self.exit_nodes: List[str] = []

        # Stack for tracking break/continue targets
        self.loop_stack: List[str] = []
        self.try_stack: List[str] = []

    def build(self, tree: ast.Module, function_name: Optional[str] = None) -> ControlFlowGraph:
        """
        Build CFG from AST.

        Args:
            tree: Parsed AST module
            function_name: If specified, build CFG only for this function

        Returns:
            Complete ControlFlowGraph
        """
        # Find target function if specified
        target_func = None
        if function_name:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
                    target_func = node
                    break
            if not target_func:
                raise ValueError(f"Function {function_name} not found")

        # Build CFG
        if target_func:
            self._build_function_cfg(target_func)
        else:
            # Build module-level CFG
            module_entry = self._create_node("entry", 1, "module_entry")
            self.entry_node = module_entry
            current_id = module_entry

            for node in tree.body:
                node_exit = self._build_statement_cfg(node, current_id, is_last_statement=True)
                if node_exit:
                    current_id = node_exit

            # Module exit
            module_exit = self._create_node("exit", len(self.source_lines) or 1, "module_exit")
            self.exit_nodes.append(module_exit)
            if current_id:
                self._create_edge(current_id, module_exit)

        return ControlFlowGraph(
            nodes=self.nodes,
            edges=self.edges,
            entry_node=self.entry_node or "",
            exit_nodes=self.exit_nodes,
        )

    def _build_function_cfg(self, func: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Build CFG for a single function."""
        # Create entry node
        entry_id = self._create_node("entry", func.lineno, f"entry_{func.name}")
        self.entry_node = entry_id

        # Build body CFG
        exit_id = self._create_node("exit", func.end_lineno or func.lineno, f"exit_{func.name}")
        self.exit_nodes.append(exit_id)

        # Connect entry to first statement
        if func.body:
            first_exit = self._build_body_cfg(func.body, entry_id)
            if first_exit:
                self._create_edge(entry_id, first_exit)

        # Any unconnected exits should connect to function exit
        for node_id in self.exit_nodes:
            if node_id != exit_id and not self._edge_exists(node_id, exit_id):
                self._create_edge(node_id, exit_id)

    def _build_body_cfg(
        self,
        body: List[ast.stmt],
        entry_id: str,
    ) -> Optional[str]:
        """
        Build CFG for a block of statements.

        Args:
            body: List of statements
            entry_id: Entry node ID

        Returns:
            Exit node ID (last node in block)
        """
        current_id = entry_id

        for i, stmt in enumerate(body):
            # Handle last statement specially
            is_last = (i == len(body) - 1)
            node_exit = self._build_statement_cfg(stmt, current_id, is_last_statement=is_last)

            if node_exit:
                current_id = node_exit

        return current_id

    def _build_statement_cfg(
        self,
        stmt: ast.stmt,
        entry_id: str,
        is_last_statement: bool = False,
    ) -> Optional[str]:
        """
        Build CFG for a single statement.

        Args:
            stmt: AST statement
            entry_id: Entry node ID
            is_last_statement: Whether this is the last statement in a block

        Returns:
            Exit node ID (where execution continues)
        """
        # If statement
        if isinstance(stmt, ast.If):
            return self._build_if_cfg(stmt, entry_id, is_last_statement)

        # For loop
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            return self._build_for_cfg(stmt, entry_id, is_last_statement)

        # While loop
        elif isinstance(stmt, ast.While):
            return self._build_while_cfg(stmt, entry_id, is_last_statement)

        # Try statement
        elif isinstance(stmt, ast.Try):
            return self._build_try_cfg(stmt, entry_id, is_last_statement)

        # Return statement
        elif isinstance(stmt, ast.Return):
            return self._build_return_cfg(stmt, entry_id)

        # Break statement
        elif isinstance(stmt, ast.Break):
            return self._build_break_cfg(stmt, entry_id)

        # Continue statement
        elif isinstance(stmt, ast.Continue):
            return self._build_continue_cfg(stmt, entry_id)

        # Raise statement
        elif isinstance(stmt, ast.Raise):
            return self._build_raise_cfg(stmt, entry_id)

        # Regular statement - create node and connect
        else:
            node_id = self._create_node("statement", stmt.lineno, self._get_stmt_label(stmt))
            self._create_edge(entry_id, node_id)
            return node_id

    def _build_if_cfg(
        self,
        if_stmt: ast.If,
        entry_id: str,
        is_last_statement: bool = False,
    ) -> Optional[str]:
        """Build CFG for if statement."""
        # Create test node
        test_id = self._create_node("branch", if_stmt.lineno, f"if_{self._get_line_source(if_stmt.lineno)}")
        self._create_edge(entry_id, test_id)

        # Build then block
        then_exit = None
        if if_stmt.body:
            then_exit = self._build_body_cfg(if_stmt.body, test_id)

        # Build else block
        else_exit = None
        if if_stmt.orelse:
            else_exit = self._build_body_cfg(if_stmt.orelse, test_id)

        # Merge point after if
        merge_id = None
        if not is_last_statement:
            merge_id = self._create_node("statement", if_stmt.end_lineno or if_stmt.lineno, "merge")

        # Connect exits to merge
        if then_exit and merge_id:
            self._create_edge(then_exit, merge_id)
        elif then_exit and is_last_statement:
            # If this is the last statement, then_exit is the if's exit
            pass

        if else_exit and merge_id:
            self._create_edge(else_exit, merge_id)
        elif else_exit and is_last_statement:
            pass

        # If no else block, connect test to merge when condition is false
        if not if_stmt.orelse and merge_id:
            self._create_edge(test_id, merge_id, condition="False")

        return merge_id or then_exit

    def _build_for_cfg(
        self,
        for_stmt: ast.For | ast.AsyncFor,
        entry_id: str,
        is_last_statement: bool = False,
    ) -> Optional[str]:
        """Build CFG for for loop."""
        # Create loop header node
        loop_id = self._create_node("loop", for_stmt.lineno, f"for_{self._get_line_source(for_stmt.lineno)}")
        self._create_edge(entry_id, loop_id)

        # Track loop for break/continue
        self.loop_stack.append(loop_id)

        # Build body directly connected to loop
        body_exit = None
        if for_stmt.body:
            # Build body starting from loop node
            for i, stmt in enumerate(for_stmt.body):
                is_last = (i == len(for_stmt.body) - 1) and is_last_statement
                node_exit = self._build_statement_cfg(stmt, loop_id, is_last_statement=is_last)
                if node_exit:
                    body_exit = node_exit

        # After body, go back to loop header
        if body_exit:
            self._create_edge(body_exit, loop_id)

        # Exit from loop (when condition is false)
        merge_id = None
        if not is_last_statement:
            merge_id = self._create_node("statement", for_stmt.end_lineno or for_stmt.lineno, "after_for")

        self._create_edge(loop_id, merge_id or "", condition="False")

        # Connect break statements to merge point
        self.loop_stack.pop()

        return merge_id

    def _build_while_cfg(
        self,
        while_stmt: ast.While,
        entry_id: str,
        is_last_statement: bool = False,
    ) -> Optional[str]:
        """Build CFG for while loop."""
        # Create loop header node
        loop_id = self._create_node("loop", while_stmt.lineno, f"while_{self._get_line_source(while_stmt.lineno)}")
        self._create_edge(entry_id, loop_id)

        # Track loop for break/continue
        self.loop_stack.append(loop_id)

        # Build body directly connected to loop
        body_exit = None
        if while_stmt.body:
            for i, stmt in enumerate(while_stmt.body):
                is_last = (i == len(while_stmt.body) - 1) and is_last_statement
                node_exit = self._build_statement_cfg(stmt, loop_id, is_last_statement=is_last)
                if node_exit:
                    body_exit = node_exit

        # After body, go back to loop header
        if body_exit:
            self._create_edge(body_exit, loop_id)

        # Exit from loop (when condition is false)
        merge_id = None
        if not is_last_statement:
            merge_id = self._create_node("statement", while_stmt.end_lineno or while_stmt.lineno, "after_while")

        self._create_edge(loop_id, merge_id or "", condition="False")

        # Connect break statements to merge point
        self.loop_stack.pop()

        return merge_id

    def _build_try_cfg(
        self,
        try_stmt: ast.Try,
        entry_id: str,
        is_last_statement: bool = False,
    ) -> Optional[str]:
        """Build CFG for try statement."""
        # Create try entry node
        try_id = self._create_node("branch", try_stmt.lineno, "try_block")
        self._create_edge(entry_id, try_id)

        # Build try body
        try_exit = None
        if try_stmt.body:
            try_exit = self._build_body_cfg(try_stmt.body, try_id)

        # Build except handlers
        handler_exits = []
        for handler in try_stmt.handlers:
            handler_id = self._create_node("branch", handler.lineno, f"except_{handler.type}")
            self._create_edge(try_id, handler_id, condition="exception")

            handler_exit = None
            if handler.body:
                handler_exit = self._build_body_cfg(handler.body, handler_id)
            handler_exits.append(handler_exit)

        # Build else block
        else_exit = None
        if try_stmt.orelse:
            else_id = self._create_node("branch", try_stmt.orelse[0].lineno, "else_block")
            self._create_edge(try_id, else_id, condition="no_exception")
            else_exit = self._build_body_cfg(try_stmt.orelse, else_id)
            handler_exits.append(else_exit)

        # Build finally block
        finally_exit = None
        if try_stmt.finalbody:
            finally_id = self._create_node("statement", try_stmt.finalbody[0].lineno, "finally_block")
            # Connect all possible paths to finally
            if try_exit:
                self._create_edge(try_exit, finally_id)
            for handler_exit in handler_exits:
                if handler_exit:
                    self._create_edge(handler_exit, finally_id)
            finally_exit = self._build_body_cfg(try_stmt.finalbody, finally_id)

        # Merge point after try
        merge_id = None
        if not is_last_statement:
            merge_id = self._create_node("statement", try_stmt.end_lineno or try_stmt.lineno, "after_try")

        # Connect to merge point
        if finally_exit:
            if merge_id:
                self._create_edge(finally_exit, merge_id)
        elif try_exit and merge_id:
            self._create_edge(try_exit, merge_id)

        for handler_exit in handler_exits:
            if handler_exit and merge_id:
                self._create_edge(handler_exit, merge_id)

        return merge_id

    def _build_return_cfg(self, return_stmt: ast.Return, entry_id: str) -> Optional[str]:
        """Build CFG for return statement."""
        node_id = self._create_node("exit", return_stmt.lineno, "return")
        self._create_edge(entry_id, node_id)
        self.exit_nodes.append(node_id)
        return None  # Return ends the path

    def _build_break_cfg(self, break_stmt: ast.Break, entry_id: str) -> Optional[str]:
        """Build CFG for break statement."""
        if not self.loop_stack:
            logger.warning("break_outside_loop", line=break_stmt.lineno)
            return None

        node_id = self._create_node("statement", break_stmt.lineno, "break")
        self._create_edge(entry_id, node_id)
        self._create_edge(node_id, self.loop_stack[-1])
        return None  # Break jumps out of current context

    def _build_continue_cfg(self, continue_stmt: ast.Continue, entry_id: str) -> Optional[str]:
        """Build CFG for continue statement."""
        if not self.loop_stack:
            logger.warning("continue_outside_loop", line=continue_stmt.lineno)
            return None

        node_id = self._create_node("statement", continue_stmt.lineno, "continue")
        self._create_edge(entry_id, node_id)
        self._create_edge(node_id, self.loop_stack[-1])
        return None  # Continue jumps to loop start

    def _build_raise_cfg(self, raise_stmt: ast.Raise, entry_id: str) -> Optional[str]:
        """Build CFG for raise statement."""
        node_id = self._create_node("exit", raise_stmt.lineno, "raise")
        self._create_edge(entry_id, node_id)
        self.exit_nodes.append(node_id)
        return None  # Raise ends the path

    def _create_node(
        self,
        node_type: str,
        line: int,
        statement: Optional[str] = None,
    ) -> str:
        """Create a CFG node."""
        node_id = f"n{self.node_counter}"
        self.node_counter += 1

        node = CFGNode(
            node_id=node_id,
            node_type=node_type,
            code_line=line,
            statement=statement,
        )
        self.nodes.append(node)
        return node_id

    def _create_edge(
        self,
        source: str,
        target: str,
        condition: Optional[str] = None,
    ) -> None:
        """Create a CFG edge."""
        if not target:  # Skip empty targets
            return

        edge = CFGEdge(source=source, target=target, condition=condition)
        self.edges.append(edge)

    def _edge_exists(self, source: str, target: str) -> bool:
        """Check if an edge exists between two nodes."""
        for edge in self.edges:
            if edge.source == source and edge.target == target:
                return True
        return False

    def _get_line_source(self, line: int) -> str:
        """Get source code for a line."""
        if 1 <= line <= len(self.source_lines):
            return self.source_lines[line - 1].strip()
        return ""

    def _get_stmt_label(self, stmt: ast.stmt) -> str:
        """Get label for a statement."""
        source = ast.unparse(stmt)
        # Truncate long statements
        if len(source) > 50:
            source = source[:47] + "..."
        return source


def build_cfg(source_code: str, function_name: Optional[str] = None) -> ControlFlowGraph:
    """
    Build control flow graph for Python code.

    Args:
        source_code: Python source code
        function_name: If specified, build CFG only for this function

    Returns:
        Complete ControlFlowGraph
    """
    try:
        tree = ast.parse(source_code)
        builder = CFGBuilder(source_code)
        cfg = builder.build(tree, function_name)

        logger.info(
            "cfg_built",
            node_count=len(cfg.nodes),
            edge_count=len(cfg.edges),
            function=function_name or "module",
        )

        return cfg

    except SyntaxError as e:
        logger.error("cfg_build_failed", error=str(e))
        raise


def visualize_cfg_dot(cfg: ControlFlowGraph) -> str:
    """
    Generate DOT format representation of CFG.

    Args:
        cfg: Control flow graph

    Returns:
        DOT format string for Graphviz
    """
    dot_lines = [
        "digraph cfg {",
        "  rankdir=TD;",
        "  node [shape=box, style=rounded];",
        "",
    ]

    # Add nodes
    for node in cfg.nodes:
        label = node.statement or node.node_type
        dot_lines.append(f'  "{node.node_id}" [label="{label}"];')

    dot_lines.append("")

    # Add edges
    for edge in cfg.edges:
        label = ""
        if edge.condition:
            label = f' [label="{edge.condition}"]'
        dot_lines.append(f'  "{edge.source}" -> "{edge.target}"{label};')

    dot_lines.append("}")
    return "\n".join(dot_lines)


def get_function_cfg(source_code: str, function_name: str) -> ControlFlowGraph:
    """
    Build CFG for a specific function.

    Args:
        source_code: Python source code
        function_name: Name of function to analyze

    Returns:
        ControlFlowGraph for the function
    """
    return build_cfg(source_code, function_name=function_name)
