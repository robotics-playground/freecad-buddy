"""Headless CLI entry (console-script ``freecad-buddy``).

``serve --transport stdio --mode inline`` runs the headless host. ``--mode rpc`` is not yet
available and returns a clear error with a non-zero exit. Diagnostics go to stderr.
"""

from __future__ import annotations

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
        if args.mode == "rpc":
            sys.stderr.write("RPC transport is not available yet; use --mode inline.\n")
            return 2
        if args.transport != "stdio":
            sys.stderr.write(
                f"transport '{args.transport}' is not available yet; use --transport stdio.\n"
            )
            return 2
        from freecad_buddy.hosts.headless.entry import run

        return run()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
