"""One or more MCP calls over :8765, logged: p0_call.py <tag> <tool> '<json args>' [<tool> '<json>' ...].

Prints each result (structuredContent, else the text blocks) and appends it to
``evidence/<tag>-mcp.jsonl``. ``$PREV.<path>`` in an argument string reads the previous result.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import mcp_client  # noqa: E402
from scenario import resolve, substitute  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent


def main():
    tag, pairs = sys.argv[1], sys.argv[2:]
    bindings = {}
    with mcp_client.McpClient() as client, (EVIDENCE / f"{tag}-mcp.jsonl").open("a", encoding="utf-8") as log:
        for tool, raw in zip(pairs[::2], pairs[1::2]):
            args = substitute(json.loads(raw), bindings)
            result = client.call(tool, args)
            bindings["PREV"] = result
            log.write(json.dumps({"mcp": tool, "args": args, "result": result}, ensure_ascii=False) + "\n")
            print(json.dumps({"mcp": tool, "args": args, "result": result}, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
