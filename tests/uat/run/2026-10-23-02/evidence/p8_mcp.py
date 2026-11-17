"""GUI-proxy MCP steps for phase P8, logged through p7_tc09.Run7 to evidence/<tag>-mcp.jsonl.

    p8_mcp.py open <tag> <absolute .FCStd path>   document_open + query_tree_summary; prints H=<handle>
    p8_mcp.py call <tag> <tool> '<json args>'      one call
"""

import json
import sys

from p7_tc09 import Run7, sc, tree_lines


def cmd_open(tag, path):
    with Run7(tag) as run:
        doc = sc(run.call("document_open", {"path": path}, "open")).get("doc")
        tree = run.call("query_tree_summary", {"doc": doc}, "tree")
        print(f"H={doc} TREE={tree_lines(tree)}")


def cmd_call(tag, tool, raw):
    with Run7(tag) as run:
        run.call(tool, json.loads(raw), "call")


if __name__ == "__main__":
    {"open": cmd_open, "call": cmd_call}[sys.argv[1]](*sys.argv[2:])
