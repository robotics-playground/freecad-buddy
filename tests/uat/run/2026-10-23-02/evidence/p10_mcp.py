"""One or more MCP calls on the :8765 proxy for phase P10 (TC-12), logged by p5_lib.Run5 to
evidence/<tag>-mcp.jsonl, each with its wall time.

    p10_mcp.py <tag> <tool> '<json>' [label] [--save=NAME=dotted.path] [--full]

"${NAME}" in the JSON is replaced by the value saved earlier in evidence/<tag>-vars.json.
--save=NAME=path stores structured_content.<dotted.path> of the result under NAME (e.g. --save=A=doc).
--full prints the whole result (a query_tree_summary text is always printed whole).
"""

import json
import re
import sys
import time
from pathlib import Path

from p5_lib import Run5

EVIDENCE = Path(__file__).resolve().parent


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    saves = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--save=")]
    full = "--full" in sys.argv
    tag, tool, payload = args[0], args[1], args[2]
    label = args[3] if len(args) > 3 else ""
    vars_file = EVIDENCE / f"{tag}-vars.json"
    saved = json.loads(vars_file.read_text(encoding="utf-8")) if vars_file.exists() else {}
    payload = re.sub(r"\$\{(\w+)\}", lambda m: saved[m.group(1)], payload)
    with Run5(tag, limit=100000 if full else 2600) as run:
        start = time.monotonic()
        result = run.call(tool, json.loads(payload), label)
        elapsed = time.monotonic() - start
        run.log.write(json.dumps({"label": label, "elapsed_s": round(elapsed, 3)}) + "\n")
    print(f"   elapsed_s={elapsed:.3f}")
    if "text" in result and not result.get("structured_content"):
        print(result["text"])
    for spec in saves:
        name, path = spec.split("=", 1)
        value = result.get("structured_content")
        for key in path.split("."):
            value = value[int(key)] if isinstance(value, list) else value[key]
        saved[name] = value
        vars_file.write_text(json.dumps(saved, indent=1), encoding="utf-8")
        print(f"   saved {name}={value}")


if __name__ == "__main__":
    main()
