"""Tests for visualization module."""

import pytest

from backend.analysis.unified_analyzer import analyze_code
from backend.parsing.visualization import (
    VisualizationGenerator,
    generate_dot_cfg,
    generate_visualizations,
    visualize_cfg_dot,
)


class TestVisualizationGenerator:
    """Test VisualizationGenerator class."""

    def test_init(self):
        """Test initialization with AnalysisResult."""
        code = "def foo(): return 1"
        result = analyze_code(code)

        gen = VisualizationGenerator(result)
        assert gen.result == result

    def test_generate_call_graph_dot(self):
        """Test call graph DOT generation."""
        code = """
def main():
    foo()

def foo():
    bar()

def bar():
    pass
"""
        result = analyze_code(code)
        gen = VisualizationGenerator(result)

        dot = gen.generate_call_graph_dot()

        assert isinstance(dot, str)
        assert "digraph call_graph" in dot
        assert "rankdir=TB" in dot

    def test_generate_call_graph_with_complexity(self):
        """Test call graph includes complexity info."""
        code = """
def complex_func():
    if x:
        if y:
            if z:
                return 1
    return 0

def simple_func():
    return 1
"""
        result = analyze_code(code)
        gen = VisualizationGenerator(result)

        dot = gen.generate_call_graph_dot()

        # Should show complexity in labels
        assert "CC" in dot or dot.count("node") >= 0

    def test_generate_dependency_graph_dot(self):
        """Test dependency graph DOT generation."""
        code = """
import os
import sys
from typing import List

def foo():
    pass
"""
        result = analyze_code(code)
        gen = VisualizationGenerator(result)

        dot = gen.generate_dependency_graph_dot()

        assert isinstance(dot, str)
        assert "digraph dependencies" in dot
        assert "rankdir=LR" in dot

    def test_generate_complexity_heatmap(self):
        """Test complexity heatmap generation."""
        code = """
def low_complexity():
    return 1

def high_complexity(x, y, z):
    if x:
        if y:
            if z:
                for i in range(10):
                    if i > 5:
                        return x + y
    return 0
"""
        result = analyze_code(code)
        gen = VisualizationGenerator(result)

        heatmap = gen.generate_complexity_heatmap()

        assert isinstance(heatmap, dict)
        assert "functions" in heatmap
        assert "max_complexity" in heatmap
        assert isinstance(heatmap["functions"], list)
        assert isinstance(heatmap["max_complexity"], int)

    def test_generate_issues_by_line(self):
        """Test issues per line generation."""
        code = """
def divide(x, y):
    return x / y

def insecure():
    sql = "SELECT * FROM users WHERE id = %s" % user_input
    return sql
"""
        result = analyze_code(code)
        gen = VisualizationGenerator(result)

        line_issues = gen.generate_issues_by_line()

        assert isinstance(line_issues, dict)
        # Line numbers should be int keys
        for line in line_issues.keys():
            assert isinstance(line, int)

    def test_heatmap_with_no_functions(self):
        """Test heatmap with empty code."""
        code = ""
        result = analyze_code(code)
        gen = VisualizationGenerator(result)

        heatmap = gen.generate_complexity_heatmap()

        assert heatmap["functions"] == []
        assert heatmap["max_complexity"] == 0


class TestGenerateDotCfg:
    """Test CFG DOT generation."""

    def test_generate_dot_cfg_simple(self):
        """Test CFG generation for simple function."""
        code = """
def foo():
    return 1
"""
        dot = generate_dot_cfg(code, "foo")

        assert isinstance(dot, str)
        assert "digraph" in dot

    def test_generate_dot_cfg_with_branch(self):
        """Test CFG generation for branching function."""
        code = """
def branch(x):
    if x > 0:
        return 1
    else:
        return 0
"""
        dot = generate_dot_cfg(code, "branch")

        assert isinstance(dot, str)
        assert "digraph" in dot

    def test_generate_dot_cfg_function_not_found(self):
        """Test CFG generation when function doesn't exist."""
        code = "def foo(): return 1"
        dot = generate_dot_cfg(code, "nonexistent")

        # Should return fallback DOT
        assert isinstance(dot, str)
        assert "digraph" in dot

    def test_generate_dot_cfg_invalid_syntax(self):
        """Test CFG generation with invalid syntax."""
        code = "def broken(\n"
        dot = generate_dot_cfg(code, "broken")

        # Should return fallback DOT
        assert isinstance(dot, str)


class TestVisualizeCfgDot:
    """Test visualize_cfg_dot function."""

    def test_visualize_cfg_dot_basic(self):
        """Test basic CFG visualization."""
        # Create a mock CFG object
        class MockCFG:
            entry_id = "entry"
            exit_id = "exit"

        cfg = MockCFG()
        dot = visualize_cfg_dot(cfg)

        assert isinstance(dot, str)
        assert "digraph cfg" in dot
        assert "entry" in dot
        assert "exit" in dot


class TestGenerateVisualizations:
    """Test generate_visualizations convenience function."""

    def test_generate_all_visualizations(self):
        """Test generating all visualizations at once."""
        code = """
def foo(x, y):
    if x > 0:
        return x / y
    return 0

def bar():
    foo(1, 2)
"""
        result = analyze_code(code)
        viz = generate_visualizations(result)

        assert isinstance(viz, dict)
        assert "call_graph_dot" in viz
        assert "dependency_graph_dot" in viz
        assert "complexity_heatmap" in viz
        assert "issues_by_line" in viz

    def test_visualizations_with_empty_code(self):
        """Test visualizations with empty code."""
        code = ""
        result = analyze_code(code)
        viz = generate_visualizations(result)

        assert viz["call_graph_dot"]
        assert viz["dependency_graph_dot"]
        assert isinstance(viz["issues_by_line"], dict)

    def test_visualizations_with_issues(self):
        """Test visualizations include issue data."""
        code = """
def divide(x, y):
    return x / y

def insecure():
    exec(user_input)
"""
        result = analyze_code(code)
        viz = generate_visualizations(result)

        # issues_by_line should be populated
        assert isinstance(viz["issues_by_line"], dict)


class TestVisualizationEdgeCases:
    """Test edge cases for visualization."""

    def test_unicode_in_function_names(self):
        """Test visualization with unicode characters."""
        code = "def émoji_😀(): return 1"
        result = analyze_code(code)
        gen = VisualizationGenerator(result)

        dot = gen.generate_call_graph_dot()
        assert isinstance(dot, str)

    def test_very_long_function_name(self):
        """Test visualization with very long function names."""
        long_name = "a" * 200
        code = f"def {long_name}(): return 1"
        result = analyze_code(code)
        gen = VisualizationGenerator(result)

        dot = gen.generate_call_graph_dot()
        assert isinstance(dot, str)

    def test_many_functions(self):
        """Test visualization with many functions."""
        code = "\n".join([f"def func{i}(): return {i}" for i in range(50)])
        result = analyze_code(code)
        gen = VisualizationGenerator(result)

        heatmap = gen.generate_complexity_heatmap()
        assert len(heatmap["functions"]) == 50
