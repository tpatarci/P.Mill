"""Command-line interface for Program Mill."""

import sys
from pathlib import Path

import structlog

logger = structlog.get_logger()


def main() -> None:
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "analyze":
        if len(sys.argv) < 3:
            print("Error: analyze command requires a file path")
            print_usage()
            sys.exit(1)
        analyze_file(sys.argv[2])

    elif command == "verify":
        if len(sys.argv) < 3:
            print("Error: verify command requires a file or directory path")
            print_usage()
            sys.exit(1)
        verify_path(sys.argv[2])

    elif command == "optimize":
        if len(sys.argv) < 3:
            print("Error: optimize command requires a file path")
            print_usage()
            sys.exit(1)
        optimize_file(sys.argv[2])

    elif command == "version":
        print("Program Mill v0.1.0")

    elif command == "help" or command == "--help" or command == "-h":
        print_usage()

    else:
        print(f"Error: Unknown command '{command}'")
        print_usage()
        sys.exit(1)


def print_usage() -> None:
    """Print CLI usage information."""
    usage = """
Program Mill - Rigorous Program Verification

Usage:
  pmill <command> [arguments]

Commands:
  analyze <file>       Analyze a single Python file
  verify <path>        Verify a file or directory
  optimize <file>      Optimize with verification guarantees
  version              Show version information
  help                 Show this help message

Examples:
  pmill analyze path/to/file.py
  pmill verify path/to/module/
  pmill optimize --verify path/to/file.py

For more information, visit: https://github.com/program-mill
"""
    print(usage)


def analyze_file(file_path: str) -> None:
    """Analyze a single file."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"Analyzing: {file_path}")
    print("Note: Full analysis pipeline not yet implemented.")
    print("This is the initial architecture phase.")
    print("\nComing soon:")
    print("  - AST parsing and structural analysis")
    print("  - Formal specification extraction")
    print("  - Multi-critic verification loop")
    print("  - Synthesis and repair suggestions")


def verify_path(path: str) -> None:
    """Verify a file or directory."""
    target = Path(path)
    if not target.exists():
        print(f"Error: Path not found: {path}")
        sys.exit(1)

    print(f"Verifying: {path}")
    print("Note: Full verification pipeline not yet implemented.")


def optimize_file(file_path: str) -> None:
    """Optimize a file with verification."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"Optimizing: {file_path}")
    print("Note: Optimization with verification not yet implemented.")


if __name__ == "__main__":
    main()
