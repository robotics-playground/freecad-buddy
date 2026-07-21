"""Headless CLI entry (console-script ``freecad-buddy``).

``serve --transport stdio --mode inline`` runs the headless host. ``serve --transport http
--mode rpc`` runs the GUI-external server that proxies tool calls to the in-FreeCAD listener.
``--mode rpc`` without ``--transport http`` is an error. Diagnostics go to stderr.
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
            if args.transport != "http":
                sys.stderr.write("--mode rpc requires --transport http.\n")
                return 2
            from freecad_buddy.hosts.gui_external.entry import run as run_rpc

            return run_rpc()
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
