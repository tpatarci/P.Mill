"""Command-line interface for Program Mill."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import structlog

from backend.analysis.unified_analyzer import analyze_code
from backend.parsing import export_report, format_console_report
from backend.parsing.visualization import generate_visualizations

logger = structlog.get_logger()


def main() -> None:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.version:
        print_version()
        return

    if args.command == "analyze":
        analyze_command(args)
    elif args.command == "verify":
        verify_command(args)
    elif args.command == "visualize":
        visualize_command(args)
    else:
        parser.print_help()
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="pmill",
        description="Program Mill - Rigorous Program Verification",
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze Python code")
    analyze_parser.add_argument(
        "file",
        type=str,
        help="Python file to analyze",
    )
    analyze_parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file path (for JSON/HTML/SARIF)",
    )
    analyze_parser.add_argument(
        "-f", "--format",
        type=str,
        choices=["json", "sarif", "html", "console"],
        default="console",
        help="Output format (default: console)",
    )
    analyze_parser.add_argument(
        "--skip-patterns",
        action="store_true",
        help="Skip design pattern detection (faster)",
    )
    analyze_parser.add_argument(
        "--skip-contracts",
        action="store_true",
        help="Skip contract analysis",
    )
    analyze_parser.add_argument(
        "--skip-invariants",
        action="store_true",
        help="Skip invariant analysis",
    )
    analyze_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress log output",
    )

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify Python code")
    verify_parser.add_argument(
        "path",
        type=str,
        help="File or directory to verify",
    )
    verify_parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict verification mode",
    )
    verify_parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output report file",
    )

    # Visualize command
    visualize_parser = subparsers.add_parser("visualize", help="Generate visualizations")
    visualize_parser.add_argument(
        "file",
        type=str,
        help="Python file to visualize",
    )
    visualize_parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default=".",
        help="Output directory for visualization files",
    )
    visualize_parser.add_argument(
        "--cfg",
        type=str,
        help="Generate CFG for specific function",
    )

    return parser


def print_version() -> None:
    """Print version information."""
    print("Program Mill v0.1.0")
    print("Rigorous Program Verification through Externalized Formal Reasoning")
    print()
    print("Analysis modules:")
    print("  - Logic critic")
    print("  - Security critic")
    print("  - Performance critic")
    print("  - Maintainability critic")
    print("  - Contract extraction")
    print("  - Invariant detection")
    print("  - Security boundary analysis")
    print()
    print("Export formats:")
    print("  - JSON, SARIF, HTML, Console")


def analyze_command(args: argparse.Namespace) -> None:
    """Execute analyze command."""
    # Configure logging
    if args.quiet:
        structlog.configure(processors=[lambda x, y: None])

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing: {args.file}")
    print("=" * 60)

    try:
        # Read source code
        source_code = file_path.read_text()

        # Run analysis
        result = analyze_code(
            source_code,
            file_path=str(file_path),
            skip_patterns=args.skip_patterns,
            skip_contracts=args.skip_contracts,
            skip_invariants=args.skip_invariants,
        )

        # Export in requested format
        output = export_report(result, format=args.format, output_path=args.output)

        if args.format == "console":
            print(output)
        else:
            print(f"\nReport generated successfully!")
            if args.output:
                print(f"Saved to: {args.output}")
            else:
                print(output)

        # Show summary
        summary = result.summary
        if "error" in summary:
            print(f"\nAnalysis error: {summary['error']}", file=sys.stderr)
            sys.exit(1)

        total_issues = summary.get("total_issues", 0)
        if total_issues > 0:
            print(f"\nFound {total_issues} issue(s) - see report for details")
            by_severity = summary.get("by_severity", {})
            for sev, count in by_severity.items():
                if count > 0:
                    print(f"  {sev.upper()}: {count}")
        else:
            print("\nNo issues found!")

    except Exception as e:
        logger.error("cli_analysis_failed", file_path=args.file, error=str(e))
        print(f"\nError during analysis: {e}", file=sys.stderr)
        sys.exit(1)


def verify_command(args: argparse.Namespace) -> None:
    """Execute verify command."""
    target = Path(args.path)
    if not target.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    print(f"Verifying: {args.path}")
    print("=" * 60)

    if target.is_file():
        verify_file(target, args.strict, args.output)
    else:
        verify_directory(target, args.strict, args.output)


def verify_file(file_path: Path, strict: bool, output: Optional[str]) -> None:
    """Verify a single file."""
    try:
        source_code = file_path.read_text()

        result = analyze_code(source_code, file_path=str(file_path))

        # Generate report
        report = export_report(result, format="json")

        # Parse results
        data = json.loads(report)
        issues = data.get("issues", {})

        security_issues = len(issues.get("security", []))
        logic_issues = len(issues.get("logic", []))
        performance_issues = len(issues.get("performance", []))
        maintainability_issues = len(issues.get("maintainability", []))

        total_issues = security_issues + logic_issues + performance_issues + maintainability_issues

        print(f"Verification complete for: {file_path}")
        print(f"  Security issues: {security_issues}")
        print(f"  Logic issues: {logic_issues}")
        print(f"  Performance issues: {performance_issues}")
        print(f"  Maintainability issues: {maintainability_issues}")
        print(f"  Total: {total_issues}")

        # Determine exit code
        if strict and total_issues > 0:
            print("\nStrict mode: failing due to issues found")
            sys.exit(1)

        if security_issues > 0:
            print("\nSecurity issues detected - review recommended")
            sys.exit(1)

        print("\nVerification passed!")

        if output:
            Path(output).write_text(report)
            print(f"Report saved to: {output}")

    except Exception as e:
        logger.error("verification_failed", file_path=str(file_path), error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def verify_directory(dir_path: Path, strict: bool, output: Optional[str]) -> None:
    """Verify all Python files in a directory."""
    python_files = list(dir_path.rglob("*.py"))

    if not python_files:
        print(f"No Python files found in: {dir_path}")
        return

    print(f"Found {len(python_files)} Python file(s)")

    all_passed = True
    results = []

    for file_path in python_files:
        try:
            source_code = file_path.read_text()
            result = analyze_code(source_code, file_path=str(file_path))

            summary = result.summary
            total_issues = summary.get("total_issues", 0)
            security_issues = len(result.security_issues)

            results.append({
                "file": str(file_path),
                "total_issues": total_issues,
                "security_issues": security_issues,
                "passed": security_issues == 0,
            })

            if security_issues > 0 or (strict and total_issues > 0):
                all_passed = False

        except Exception as e:
            logger.warning("file_verification_failed", file=str(file_path), error=str(e))
            results.append({
                "file": str(file_path),
                "error": str(e),
                "passed": False,
            })
            all_passed = False

    # Print summary
    print("\n" + "=" * 60)
    print("Verification Summary:")
    print("=" * 60)

    for r in results:
        status = "PASS" if r.get("passed", False) else "FAIL"
        print(f"  [{status}] {r['file']}")
        if "error" in r:
            print(f"        Error: {r['error']}")
        else:
            print(f"        Issues: {r.get('total_issues', 0)} (Security: {r.get('security_issues', 0)})")

    print("=" * 60)

    if all_passed:
        print("\nAll files passed verification!")
    else:
        print("\nSome files failed verification")
        sys.exit(1)

    if output:
        Path(output).write_text(json.dumps(results, indent=2))
        print(f"Report saved to: {output}")


def visualize_command(args: argparse.Namespace) -> None:
    """Execute visualize command."""
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    print(f"Generating visualizations for: {args.file}")

    try:
        source_code = file_path.read_text()
        result = analyze_code(source_code, file_path=str(file_path))

        # Generate visualizations
        viz = generate_visualizations(result)

        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = file_path.stem

        # Save DOT files
        call_graph_path = output_dir / f"{base_name}_call_graph.dot"
        call_graph_path.write_text(viz["call_graph_dot"])
        print(f"Call graph: {call_graph_path}")

        dep_graph_path = output_dir / f"{base_name}_dependencies.dot"
        dep_graph_path.write_text(viz["dependency_graph_dot"])
        print(f"Dependency graph: {dep_graph_path}")

        # Save heatmap as JSON
        heatmap_path = output_dir / f"{base_name}_heatmap.json"
        heatmap_path.write_text(json.dumps(viz["complexity_heatmap"], indent=2))
        print(f"Complexity heatmap: {heatmap_path}")

        # Generate CFG if requested
        if args.cfg:
            from backend.parsing.visualization import generate_dot_cfg

            cfg_dot = generate_dot_cfg(source_code, args.cfg)
            cfg_path = output_dir / f"{base_name}_{args.cfg}_cfg.dot"
            cfg_path.write_text(cfg_dot)
            print(f"CFG for '{args.cfg}': {cfg_path}")

        print(f"\nVisualization files saved to: {output_dir}")
        print("\nTo render DOT files, use Graphviz:")
        print("  dot -Tpng call_graph.dot -o call_graph.png")
        print("  dot -Tsvg dependencies.dot -o dependencies.svg")

    except Exception as e:
        logger.error("visualization_failed", file_path=args.file, error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
