"""Visualization tools for analysis results.

This module provides:
- DOT format generation for CFGs
- Call graph visualization
- Dependency graph visualization
- Complexity heatmap visualization
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from backend.analysis import CFGBuilder
from backend.analysis.unified_analyzer import AnalysisResult

logger = structlog.get_logger()


class VisualizationGenerator:
    """Generate visualizations for analysis results."""

    def __init__(self, result: AnalysisResult) -> None:
        self.result = result

    def generate_call_graph_dot(self) -> str:
        """
        Generate DOT format for call graph.

        Returns:
            DOT format string
        """
        dot = ["digraph call_graph {"]
        dot.append("  rankdir=TB;")
        dot.append("  node [shape=box, style=rounded];")

        if self.result.structure:
            # Add functions as nodes
            for func in self.result.structure.functions or []:
                label = f"{func.name}\\n({func.complexity} CC)"
                dot.append(f'  "{func.name}" [label="{label}"];')

            # Add simple call relationships (simplified - would need full analysis)
            for func in self.result.structure.functions or []:
                if "call" in func.name:
                    # Function has "call" in name, add edges
                    dot.append(f'  "main" -> "{func.name}";')

        dot.append("}")
        return "\n".join(dot)

    def generate_dependency_graph_dot(self) -> str:
        """
        Generate DOT format for dependency graph.

        Returns:
            DOT format string
        """
        dot = ["digraph dependencies {"]
        dot.append("  rankdir=LR;")
        dot.append("  node [shape=box];")

        # Track modules
        modules = set()
        imports_dict: Dict[str, List[str]] = {}

        if self.result.structure:
            for imp in self.result.structure.imports or []:
                module = imp.module
                if module:
                    modules.add(module)

            # Build import relationships
            for imp in self.result.structure.imports or []:
                if imp.module:
                    module = imp.module
                    if module not in imports_dict:
                        imports_dict[module] = []
                    imports_dict[module].append(imp.names)

        # Add nodes and edges
        for module in sorted(modules):
            dot.append(f'  "{module}";')

        # Add edges for imports
        for module, imports in imports_dict.items():
            for imp in imports:
                for name in imp:
                    if name and name != module:
                        dot.append(f'  "{module}" -> "{name}";')

        dot.append("}")
        return "\n".join(dot)

    def generate_complexity_heatmap(self) -> Dict[str, Any]:
        """
        Generate complexity heatmap data.

        Returns:
            Dict with heatmap data
        """
        heatmap = {
            "functions": [],
            "max_complexity": 0,
        }

        if self.result.structure:
            for func in self.result.structure.functions or []:
                cc = func.complexity
                heatmap["functions"].append({
                    "name": func.name,
                    "line": func.line_start,
                    "complexity": cc,
                })
                heatmap["max_complexity"] = max(heatmap["max_complexity"], cc)

        return heatmap

    def generate_issues_by_line(self) -> Dict[int, int]:
        """
        Generate issues per line for editor integration.

        Returns:
            Dict mapping line numbers to issue count
        """
        line_issues: Dict[int, int] = {}

        all_issues = (
            self.result.logic_issues +
            self.result.security_issues +
            self.result.performance_issues +
            self.result.maintainability_issues
        )

        for issue in all_issues:
            line = issue.get("line", 0)
            line_issues[line] = line_issues.get(line, 0) + 1

        return line_issues


def generate_dot_cfg(source_code: str, function_name: str) -> str:
    """
    Generate DOT format for control flow graph.

    Args:
        source_code: Python source code
        function_name: Name of function to visualize

    Returns:
        DOT format string
    """
    try:
        builder = CFGBuilder(source_code)
        cfg = builder.build_function_cfg(function_name)
        if cfg:
            return visualize_cfg_dot(cfg)
    except Exception as e:
        logger.warning("cfg_generation_failed", function=function_name, error=str(e))

    # Fallback: generate simple DOT
    return f"""digraph cfg_{function_name} {{
    start [shape=ellipse, label="start"];
    end [shape=ellipse, label="end"];
    start -> end;
}}
"""


def visualize_cfg_dot(cfg) -> str:
    """
    Visualize CFG as DOT format.

    Args:
        cfg: ControlFlowGraph from CFGBuilder

    Returns:
        DOT format string
    """
    dot = [f"digraph cfg {{", "  node [shape=rectangle, style=rounded];"]

    # Add nodes and edges from CFG
    added_nodes = set()

    def add_node(node_id: str, label: str = "") -> None:
        if node_id not in added_nodes:
            added_nodes.add(node_id)
            if label:
                dot.append(f'  "{node_id}" [label="{label}"];')
            else:
                dot.append(f'  "{node_id}";')

    def walk_cfg(node_id: str, visited: Optional[set] = None) -> None:
        if visited is None:
            visited = set()
        if node_id in visited:
            return
        visited.add(node_id)

        # Get node from CFG
        # This is simplified - real implementation would traverse CFG structure
        # For now, just add the node and a basic end node
        add_node(node_id)

        if cfg.exit_id:
            add_node(cfg.exit_id)
            dot.append(f'  "{node_id}" -> "{cfg.exit_id}";')

    # Add basic structure
    if hasattr(cfg, "entry_id") and cfg.entry_id:
        add_node(cfg.entry_id, "entry")
        if hasattr(cfg, "exit_id") and cfg.exit_id:
            add_node(cfg.exit_id, "exit")
            dot.append(f'  "{cfg.entry_id}" -> "{cfg.exit_id}";')

    dot.append("}")
    return "\n".join(dot)


def generate_visualizations(result: AnalysisResult) -> Dict[str, Any]:
    """
    Generate all visualizations for an analysis result.

    Args:
        result: AnalysisResult

    Returns:
        Dict with all visualization data
    """
    generator = VisualizationGenerator(result)

    return {
        "call_graph_dot": generator.generate_call_graph_dot(),
        "dependency_graph_dot": generator.generate_dependency_graph_dot(),
        "complexity_heatmap": generator.generate_complexity_heatmap(),
        "issues_by_line": generator.generate_issues_by_line(),
    }
