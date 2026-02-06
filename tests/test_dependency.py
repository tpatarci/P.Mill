"""Tests for dependency analysis."""

import tempfile
from pathlib import Path

import pytest

from backend.analysis.dependency import (
    _get_stdlib_modules,
    build_dependency_graph,
    detect_circular_dependencies,
    find_unused_imports,
)
from backend.models import ImportInfo


class TestDependencyGraph:
    """Test dependency graph building."""

    def test_empty_graph(self):
        """Test empty dependency graph."""
        from backend.analysis.dependency import DependencyGraph

        graph = DependencyGraph()

        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
        assert len(graph.imports_by_file) == 0

    def test_add_node(self):
        """Test adding nodes to graph."""
        from backend.analysis.dependency import DependencyGraph

        graph = DependencyGraph()
        graph.add_node("module_a")

        assert "module_a" in graph.nodes
        assert "module_a" in graph.edges

    def test_add_dependency(self):
        """Test adding dependency edges."""
        from backend.analysis.dependency import DependencyGraph

        graph = DependencyGraph()
        graph.add_dependency("module_a", "module_b")

        assert "module_a" in graph.nodes
        assert "module_b" in graph.nodes
        assert "module_b" in graph.edges["module_a"]

    def test_find_circular_dependencies_none(self):
        """Test finding circular dependencies when none exist."""
        from backend.analysis.dependency import DependencyGraph

        graph = DependencyGraph()
        graph.add_dependency("module_a", "module_b")
        graph.add_dependency("module_c", "module_a")

        cycles = graph.find_circular_dependencies()

        assert len(cycles) == 0

    def test_find_circular_dependencies_simple(self):
        """Test finding simple circular dependency."""
        from backend.analysis.dependency import DependencyGraph

        graph = DependencyGraph()
        graph.add_dependency("module_a", "module_b")
        graph.add_dependency("module_b", "module_a")

        cycles = graph.find_circular_dependencies()

        assert len(cycles) == 1
        # Cycle could be ['module_a', 'module_b'] or ['module_b', 'module_a']
        assert set(cycles[0]) == {"module_a", "module_b"}

    def test_find_circular_dependencies_complex(self):
        """Test finding complex circular dependencies."""
        from backend.analysis.dependency import DependencyGraph

        graph = DependencyGraph()
        graph.add_dependency("module_a", "module_b")
        graph.add_dependency("module_b", "module_c")
        graph.add_dependency("module_c", "module_a")

        cycles = graph.find_circular_dependencies()

        assert len(cycles) >= 1

    def test_transitive_dependencies(self):
        """Test getting transitive dependencies."""
        from backend.analysis.dependency import DependencyGraph

        graph = DependencyGraph()
        graph.add_dependency("module_a", "module_b")
        graph.add_dependency("module_b", "module_c")

        transitive = graph.get_transitive_dependencies("module_a")

        assert "module_a" in transitive
        assert "module_b" in transitive
        assert "module_c" in transitive

    def test_reverse_dependencies(self):
        """Test getting reverse dependencies."""
        from backend.analysis.dependency import DependencyGraph

        graph = DependencyGraph()
        graph.add_dependency("module_a", "module_c")
        graph.add_dependency("module_b", "module_c")

        reverse = graph.get_reverse_dependencies("module_c")

        assert "module_c" in reverse
        assert "module_a" in reverse
        assert "module_b" in reverse


class TestUnusedImports:
    """Test unused import detection."""

    def test_no_unused_imports(self):
        """Test file with all imports used."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
import os
import sys

def foo():
    path = os.path.join("a", "b")
    return sys.version
""")
            temp_path = f.name

        try:
            unused = find_unused_imports(temp_path)
            assert len(unused) == 0
        finally:
            Path(temp_path).unlink()

    def test_unused_import_detected(self):
        """Test that unused imports are detected."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
import os
import sys

def foo():
    return sys.version
""")
            temp_path = f.name

        try:
            unused = find_unused_imports(temp_path)
            assert len(unused) == 1
            assert unused[0].module == "os"
        finally:
            Path(temp_path).unlink()

    def test_from_import_unused(self):
        """Test unused 'from' import."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
from os import path
from sys import version

def foo():
    return version
""")
            temp_path = f.name

        try:
            unused = find_unused_imports(temp_path)
            assert len(unused) == 1
            assert unused[0].module == "os"
            assert "path" in unused[0].names
        finally:
            Path(temp_path).unlink()

    def test_alias_used_directly(self):
        """Test that import with alias is used."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
import os as operating_system

def foo():
    return operating_system.path
""")
            temp_path = f.name

        try:
            unused = find_unused_imports(temp_path)
            assert len(unused) == 0
        finally:
            Path(temp_path).unlink()

    def test_star_import_always_used(self):
        """Test that star imports are never marked unused."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
from os import *

def foo():
    return path.join("a", "b")
""")
            temp_path = f.name

        try:
            unused = find_unused_imports(temp_path)
            # Star imports are always considered "used"
            assert len(unused) == 0
        finally:
            Path(temp_path).unlink()

    def test_module_attribute_usage(self):
        """Test that using module.function counts as using import."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
import collections

def foo():
    return collections.Counter()
""")
            temp_path = f.name

        try:
            unused = find_unused_imports(temp_path)
            # collections.Counter uses the module
            assert len(unused) == 0
        finally:
            Path(temp_path).unlink()


class TestCircularDepsDetection:
    """Test circular dependency detection in real code."""

    def test_no_circular_deps(self):
        """Test directory without circular dependencies."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create non-circular imports
            # file_a.py imports nothing
            # file_b.py imports file_a
            # file_c.py imports file_b

            file_a = Path(tmpdir) / "file_a.py"
            file_b = Path(tmpdir) / "file_b.py"
            file_c = Path(tmpdir) / "file_c.py"

            file_a.write_text("x = 1\n")
            file_b.write_text("import file_a\n")
            file_c.write_text("import file_b\n")

            cycles = detect_circular_dependencies(tmpdir)
            assert len(cycles) == 0

    def test_circular_deps_detected(self):
        """Test directory with circular dependencies."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create circular imports
            # file_a.py imports file_b
            # file_b.py imports file_a

            file_a = Path(tmpdir) / "file_a.py"
            file_b = Path(tmpdir) / "file_b.py"

            file_a.write_text("import file_b\n")
            file_b.write_text("import file_a\n")

            cycles = detect_circular_dependencies(tmpdir)
            assert len(cycles) >= 1


class TestStdlibModules:
    """Test standard library module detection."""

    def test_stdlib_modules_populated(self):
        """Test that stdlib modules set is populated."""
        stdlib = _get_stdlib_modules()

        # Should contain common modules
        assert "os" in stdlib
        assert "sys" in stdlib
        assert "json" in stdlib
        assert "pathlib" in stdlib

    def test_stdlib_does_not_change(self):
        """Test that stdlib modules is stable."""
        stdlib1 = _get_stdlib_modules()
        stdlib2 = _get_stdlib_modules()

        assert stdlib1 == stdlib2


class TestImportExtraction:
    """Test import extraction from AST."""

    def test_extract_import(self):
        """Test extracting import statement."""
        code = """
import os
import sys
"""
        import ast
        from backend.analysis.dependency import _extract_imports_from_tree

        tree = ast.parse(code)
        imports = _extract_imports_from_tree(tree)

        assert len(imports) == 2
        modules = {imp.module for imp in imports}
        assert "os" in modules
        assert "sys" in modules

    def test_extract_from_import(self):
        """Test extracting from import statement."""
        code = """
from os import path
from sys import argv
"""
        import ast
        from backend.analysis.dependency import _extract_imports_from_tree

        tree = ast.parse(code)
        imports = _extract_imports_from_tree(tree)

        assert len(imports) == 2
        assert all(imp.is_from for imp in imports)

    def test_extract_import_with_alias(self):
        """Test extracting import with alias."""
        code = """
import numpy as np
"""
        import ast
        from backend.analysis.dependency import _extract_imports_from_tree

        tree = ast.parse(code)
        imports = _extract_imports_from_tree(tree)

        assert len(imports) == 1
        assert imports[0].alias == "np"
        assert imports[0].module == "numpy"

    def test_extract_from_import_with_alias(self):
        """Test extracting from import with alias."""
        code = """
from os import path as p
"""
        import ast
        from backend.analysis.dependency import _extract_imports_from_tree

        tree = ast.parse(code)
        imports = _extract_imports_from_tree(tree)

        assert len(imports) == 1
        assert imports[0].alias == "p"
        assert imports[0].module == "os"

    def test_extract_nested_imports(self):
        """Test extracting imports from nested code."""
        code = """
import os

class MyClass:
    import sys

    def method(self):
        import json
        return os.path
"""
        import ast
        from backend.analysis.dependency import _extract_imports_from_tree

        tree = ast.parse(code)
        imports = _extract_imports_from_tree(tree)

        # Should find all 4 imports (os, sys, json)
        assert len(imports) >= 3
