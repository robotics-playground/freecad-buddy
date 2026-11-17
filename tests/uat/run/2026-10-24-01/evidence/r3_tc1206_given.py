"""TC-12-06 Given over MCP: document with a padded Body (20 x 20 mm sketch, 30 mm pad), then the outside topology oracle
(script_exec on Pad.Shape.Edges) names one vertical edge. Saves doc and edge to tc-12-06-vars.json."""
import json
from pathlib import Path
from r2_p5_lib import Run5

EVIDENCE = Path(__file__).resolve().parent
ORACLE = ("import FreeCAD\nshape = doc.getObject('Pad').Shape\nres = []\n"
          "for i, e in enumerate(shape.Edges, 1):\n"
          "    a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point\n"
          "    if abs(a.x - b.x) < 1e-6 and abs(a.y - b.y) < 1e-6 and abs(a.z - b.z) > 1:\n"
          "        res.append(['Edge%d' % i, [round(a.x, 3), round(a.y, 3), round(a.z, 3)], [round(b.x, 3), round(b.y, 3), round(b.z, 3)]])\n"
          "result = res")
with Run5("tc-12-06") as run:
    doc = run.fixture_pad("TC1206")
    out = run.call("script_exec", {"doc": doc, "code": ORACLE}, "edge oracle")
    run.call("query_tree_summary", {"doc": doc}, "given tree")
    vars_file = EVIDENCE / "tc-12-06-vars.json"
    vars_file.write_text(json.dumps({"D": doc, "oracle": out["structured_content"]["value_repr"]}), encoding="utf-8")
    print("doc", doc)
