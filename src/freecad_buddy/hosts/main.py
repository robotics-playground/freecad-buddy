"""Headless CLI entry (console-script ``freecad-buddy``).

Phase-0 stub: parses a ``serve`` subcommand and returns. No print() (ruff T201);
diagnostics go to stderr. Transport/mode wiring lands in story 1.4.
"""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="freecad-buddy")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the MCP bridge")
    serve.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    serve.add_argument("--mode", choices=["inline", "rpc"], default="inline")

    args = parser.parse_args(argv)

    if args.command == "serve":
        sys.stderr.write(
            f"serve stub: transport={args.transport} mode={args.mode} (not implemented yet)\n"
        )
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
