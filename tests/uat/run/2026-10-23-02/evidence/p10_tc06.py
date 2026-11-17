"""TC-12-06 MCP steps for phase P10, logged by p5_lib.Run5 to evidence/tc-12-06-mcp.jsonl.

    p10_tc06.py given     padded body (p4_lib fixture_pad, 20 x 20 x 30) and the vertical edges of Pad
    p10_tc06.py fillet <edge>   preview_dry_run, then feature_fillet with the preview's confirm
"""
import json
import sys
from pathlib import Path

from p5_lib import Run5

EVIDENCE = Path(__file__).resolve().parent
VARS = EVIDENCE / "tc-12-06-vars.json"
EDGES = ("pad = doc.getObject('Pad')\nresult = [(f'Edge{i}', round(e.Vertexes[0].Point.z, 3), round(e.Vertexes[-1].Point.z, 3))"
         " for i, e in enumerate(pad.Shape.Edges, 1) if abs(e.Vertexes[0].Point.z - e.Vertexes[-1].Point.z) > 1e-6]")

with Run5("tc-12-06") as run:
    if sys.argv[1] == "given":
        doc = run.fixture_pad("TC1206")
        VARS.write_text(json.dumps({"H": doc}), encoding="utf-8")
        run.call("query_tree_summary", {"doc": doc}, "given tree")
        run.call("script_exec", {"doc": doc, "code": EDGES}, "given vertical edges (outside oracle)")
    else:
        doc = json.loads(VARS.read_text(encoding="utf-8"))["H"]
        args = {"body": "Body", "base": "Pad", "name": "Fillet",
                "edges": [{"kind": "mapped_name", "object": "Pad", "mapped_name": sys.argv[2]}],
                "radius": {"value": 3, "unit": "mm"}}
        run.mut(doc, "feature_fillet", args, "when fillet")
