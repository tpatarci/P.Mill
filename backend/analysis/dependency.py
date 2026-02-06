"""Dependency analysis for Python code."""

import ast
from typing import Dict, List, Optional, Set, Tuple

import structlog

from backend.models import ImportInfo

logger = structlog.get_logger()


class DependencyGraph:
    """Dependency graph for module imports."""

    def __init__(self):
        """Initialize dependency graph."""
        self.nodes: Set[str] = set()  # Module/file names
        self.edges: Dict[str, Set[str]] = {}  # source -> set of dependencies
        self.imports_by_file: Dict[str, List[ImportInfo]] = {}

    def add_node(self, name: str) -> None:
        """Add a node to the graph."""
        self.nodes.add(name)
        if name not in self.edges:
            self.edges[name] = set()

    def add_dependency(self, source: str, target: str) -> None:
        """Add a dependency edge from source to target."""
        self.add_node(source)
        self.add_node(target)
        self.edges[source].add(target)

    def add_import(self, file_path: str, import_info: ImportInfo) -> None:
        """Add an import to the graph."""
        if file_path not in self.imports_by_file:
            self.imports_by_file[file_path] = []
        self.imports_by_file[file_path].append(import_info)

        # Add dependency edge
        # For 'from X import Y', dependency is on X
        # For 'import X', dependency is on X
        if import_info.module:
            self.add_dependency(file_path, import_info.module)

    def find_circular_dependencies(self) -> List[List[str]]:
        """
        Find circular dependencies using DFS.

        Returns:
            List of cycles (each cycle is a list of module names)
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            """DFS to detect cycles."""
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]

            if node in visited:
                return None

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.edges.get(node, []):
                cycle = dfs(neighbor, path)
                if cycle:
                    return cycle

            path.pop()
            rec_stack.remove(node)
            return None

        for node in self.nodes:
            if node not in visited:
                cycle = dfs(node, [])
                if cycle:
                    cycles.append(cycle)

        return cycles

    def get_transitive_dependencies(self, module: str) -> Set[str]:
        """
        Get all transitive dependencies of a module.

        Args:
            module: Module name

        Returns:
            Set of all transitively imported modules
        """
        visited = set()

        def dfs(node: str) -> None:
            if node in visited:
                return
            visited.add(node)
            for neighbor in self.edges.get(node, []):
                dfs(neighbor)

        dfs(module)
        return visited

    def get_reverse_dependencies(self, module: str) -> Set[str]:
        """
        Get all modules that (transitively) depend on this module.

        Args:
            module: Module name

        Returns:
            Set of all modules that import this module
        """
        reverse_edges: Dict[str, Set[str]] = {}
        for source, targets in self.edges.items():
            for target in targets:
                if target not in reverse_edges:
                    reverse_edges[target] = set()
                reverse_edges[target].add(source)

        visited = set()

        def dfs(node: str) -> None:
            if node in visited:
                return
            visited.add(node)
            for neighbor in reverse_edges.get(node, []):
                dfs(neighbor)

        dfs(module)
        return visited


def build_dependency_graph(file_paths: List[str]) -> DependencyGraph:
    """
    Build dependency graph from a list of Python files.

    Args:
        file_paths: List of paths to Python files

    Returns:
        DependencyGraph containing all import dependencies
    """
    graph = DependencyGraph()

    for file_path in file_paths:
        try:
            with open(file_path, 'r') as f:
                source_code = f.read()
                tree = ast.parse(source_code)

            # Extract imports
            imports = _extract_imports_from_tree(tree)

            for imp in imports:
                graph.add_import(file_path, imp)

        except Exception as e:
            logger.warning("dependency_parse_failed", file=file_path, error=str(e))

    return graph


def find_unused_imports(file_path: str) -> List[ImportInfo]:
    """
    Find unused imports in a Python file.

    An import is considered unused if the imported name is not
    referenced anywhere in the file.

    Args:
        file_path: Path to Python file

    Returns:
        List of unused ImportInfo objects
    """
    try:
        with open(file_path, 'r') as f:
            source_code = f.read()

        tree = ast.parse(source_code)
        imports = _extract_imports_from_tree(tree)

        if not imports:
            return []

        # Get all names used in the code
        used_names = _get_used_names(tree)

        unused = []
        for imp in imports:
            is_used = False

            # Check if any imported name is used
            for name in imp.names:
                if name == "*":
                    # Star imports are always considered "used"
                    is_used = True
                    break
                elif name in used_names:
                    is_used = True
                    break

            # Check if alias is used
            if imp.alias and imp.alias in used_names:
                is_used = True

            # Check if module itself is used (for 'import module' without specific names)
            if not imp.names and imp.module:
                # For 'import os', check if 'os' is used or 'os.something' is used
                if imp.module in used_names:
                    is_used = True
                else:
                    module_prefix = imp.module + "."
                    for used in used_names:
                        if used.startswith(module_prefix):
                            is_used = True
                            break

            if not is_used:
                unused.append(imp)

        return unused

    except Exception as e:
        logger.warning("unused_import_check_failed", file=file_path, error=str(e))
        return []


def _extract_imports_from_tree(tree: ast.Module) -> List[ImportInfo]:
    """Extract imports from an AST tree."""
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportInfo(
                    module=alias.name,
                    names=[],
                    alias=alias.asname,
                    line=node.lineno,
                    is_from=False,
                ))

        elif isinstance(node, ast.ImportFrom):
            names = [alias_node.name for alias_node in node.names]
            alias = node.names[0].asname if node.names and node.names[0].asname else None

            imports.append(ImportInfo(
                module=node.module or "",
                names=names,
                alias=alias,
                line=node.lineno,
                is_from=True,
            ))

    return imports


def _get_used_names(tree: ast.Module) -> Set[str]:
    """Get all names used in the code."""
    used_names = set()

    class NameVisitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            used_names.add(node.id)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            # Get the base name for attributes
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)
            self.generic_visit(node)

    visitor = NameVisitor()
    visitor.visit(tree)

    return used_names


def detect_circular_dependencies(directory: str) -> List[List[str]]:
    """
    Detect circular dependencies in a directory of Python files.

    Args:
        directory: Path to directory containing Python files

    Returns:
        List of cycles (each cycle is a list of module/file names)
    """
    import os
    from pathlib import Path

    python_files = [str(p) for p in Path(directory).rglob("*.py")]
    graph = DependencyGraph()

    for file_path in python_files:
        try:
            with open(file_path, 'r') as f:
                source_code = f.read()
                tree = ast.parse(source_code)

            imports = _extract_imports_from_tree(tree)

            for imp in imports:
                # Convert import to file path if it's a local module
                dep_path = _resolve_import_to_file(file_path, imp.module, directory)
                if dep_path:
                    graph.add_dependency(file_path, dep_path)

        except Exception as e:
            logger.warning("circular_dep_parse_failed", file=file_path, error=str(e))

    return graph.find_circular_dependencies()


def _resolve_import_to_file(
    source_file: str,
    import_module: str,
    base_dir: str
) -> Optional[str]:
    """
    Resolve an import module to a file path.

    Args:
        source_file: File containing the import
        import_module: Module being imported
        base_dir: Base directory for resolving paths

    Returns:
        Resolved file path or None if not a local module
    """
    # Skip standard library and third-party modules
    if import_module in _get_stdlib_modules():
        return None

    from pathlib import Path

    source_dir = Path(source_file).parent

    # Try to find the module as a file
    # First, try same directory
    module_file = source_dir / f"{import_module}.py"
    if module_file.exists():
        return str(module_file)

    # Try as package (with __init__.py)
    module_dir = source_dir / import_module
    init_file = module_dir / "__init__.py"
    if init_file.exists():
        return str(init_file)

    # Try parent directories
    for parent in Path(source_file).parents:
        module_file = parent / f"{import_module}.py"
        if module_file.exists():
            return str(module_file)

        module_dir = parent / import_module
        init_file = module_dir / "__init__.py"
        if init_file.exists():
            return str(init_file)

    return None


def _get_stdlib_modules() -> Set[str]:
    """Return set of Python standard library module names."""
    return {
        "abc", "aifc", "argparse", "array", "ast", "asyncio", "atexit", "audioop",
        "base64", "binascii", "binhex", "bisect", "builtins", "bz2", "calendar",
        "cgi", "cgitb", "chunk", "cmath", "cmd", "code", "codecs", "codeop",
        "collections", "colorsys", "compileall", "concurrent", "configparser",
        "contextlib", "contextvars", "copy", "copyreg", "cProfile", "crypt",
        "csv", "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal",
        "difflib", "dis", "distutils", "doctest", "email", "encodings", "enum",
        "errno", "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch",
        "formatter", "fractions", "ftplib", "functools", "gc", "getopt", "getpass",
        "getpass", "glob", "graphlib", "grp", "gzip", "hashlib", "heapq", "hmac",
        "help", "heapq", "html", "http", "http.client", "http.server", "imaplib",
        "imghdr", "imp", "inspect", "io", "ipaddress", "itertools", "json",
        "keyword", "lib2parse", "linecache", "locale", "logging", "lzma",
        "marshal", "math", "mimetypes", "mmap", "modulefinder", "msilib",
        "multiprocessing", "netrc", "nis", "nntplib", "numbers", "operator",
        "optparse", "os", "ossaudiodev", "pathlib", "pdb", "pickle", "pickletools",
        "pipes", "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath",
        "pprint", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue",
        "quopri", "random", "re", "readline", "reprlib", "resource",
        "rlcompleter", "runpy", "sched", "secrets", "select", "selectors",
        "shelve", "shlex", "shutil", "signal", "site", "smtpd", "smtplib",
        "sndhdr", "socket", "socketserver", "spwd", "sqlite3", "ssl", "stat",
        "statistics", "string", "stringprep", "struct", "subprocess", "sys",
        "sysconfig", "tarfile", "telnetlib", "tempfile", "termios", "textwrap",
        "threading", "time", "timeit", "tkinter", "tokenize", "tomllib", "trace",
        "traceback", "tracemalloc", "tty", "turtle", "types", "typing", "unicodedata",
        "unittest", "urllib", "urllib.parse", "urllib.request", "urllib.response",
        "urllib.error", "uuid", "venv", "warnings", "wave", "weakref", "webbrowser",
        "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc", "xmlrpc.client",
        "xmlrpc.server", "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo",
    }
