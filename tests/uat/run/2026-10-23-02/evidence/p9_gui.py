"""MCP calls on the :8765 proxy for phase P9 (TC-11), logged by p5_lib.Run5 to evidence/<tag>-mcp.jsonl.

    p9_gui.py open <tag>                 document_open the golden box; the handle goes to evidence/<tag>-handle.txt
    p9_gui.py fit <tag>                  Show All (p1_gui.py showall), then view_fit_viewport on the handle
    p9_gui.py close <tag>                document_close the handle
    p9_gui.py call <tag> <tool> '<json>' one call; "$H" in the JSON is the recorded handle
"""

import json
import subprocess
import sys
from pathlib import Path

from p5_lib import Run5

EVIDENCE = Path(__file__).resolve().parent
BOX = str(EVIDENCE.parents[4] / "benchmarks" / "g0" / "golden-models" / "box-10-20-30.FCStd")


def handle(tag):
    return (EVIDENCE / f"{tag}-handle.txt").read_text(encoding="utf-8").strip()


def main():
    action, tag, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
    with Run5(tag) as run:
        if action == "open":
            result = run.call("document_open", {"path": BOX}, "given open box")
            (EVIDENCE / f"{tag}-handle.txt").write_text(result["structured_content"]["doc"], encoding="utf-8")
        elif action == "fit":
            print(subprocess.run([sys.executable, str(EVIDENCE / "p1_gui.py"), "showall"], capture_output=True,
                                 text=True, cwd=EVIDENCE).stdout.strip()[:400])
            run.call("view_fit_viewport", {"doc": handle(tag)}, "fit")
        elif action == "close":
            run.call("document_close", {"doc": handle(tag)}, "cleanup close")
        elif action == "call":
            args = json.loads(rest[1].replace("$H", handle(tag)))
            run.call(rest[0], args, rest[2] if len(rest) > 2 else "")


if __name__ == "__main__":
    main()
