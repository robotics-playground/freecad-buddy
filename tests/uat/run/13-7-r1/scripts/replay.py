"""CAP-1 replay for query_interference through the container bridge."""
import ast, asyncio, json, sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcpcall import call_many
OUT = r"D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-7-r1"

BUILD = '''
import Part, FreeCAD as App
def add(n, s):
    o = doc.addObject("Part::Feature", n); o.Shape = s
V = App.Vector
add("A", Part.makeBox(10, 10, 10))                       # reference box
add("Sep", Part.makeBox(10, 10, 10, V(20, 0, 0)))        # 10 mm gap from A
add("Over", Part.makeBox(10, 10, 10, V(5, 5, 5)))        # 5x5x5 overlap with A = 125
add("FaceTouch", Part.makeBox(10, 10, 10, V(0, 0, 10)))  # shares A's top face
add("VertTouch", Part.makeBox(10, 10, 10, V(-10, -10, -10)))  # shares one vertex with A
add("Cyl", Part.makeCylinder(3, 30, V(5, 5, -10)))       # through A: pi*9*10
c = [(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)]
add("Bowtie", Part.Face(Part.makePolygon([V(x, y, 0) for x, y in c])).extrude(V(0, 0, 10)))
doc.recompute()
result = "built"
'''
STATE = '''
import json
from freecad_buddy.usecases.fingerprint import fingerprint
result = json.dumps({"digest": fingerprint(doc, fresh=True)["digest"], "undo": doc.UndoCount,
  "names": [o.Name for o in doc.Objects],
  "placements": {o.Name: [round(x, 9) for x in o.Placement.Base] + [round(x, 9) for x in o.Placement.Rotation.Q] for o in doc.Objects},
  "touched": [o.Name for o in doc.Objects if "Touched" in o.State]})
'''
def script_pairs(pairs):
    return '''
import json, math
out = []
for a, b in %r:
    sa, sb = doc.getObject(a).Shape, doc.getObject(b).Shape
    try:
        cm = sa.common(sb); vol = cm.Volume; nsub = len(cm.SubShapes); bbv = cm.BoundBox.isValid(); err = None
    except Exception as e:
        vol = None; nsub = None; bbv = None; err = repr(e)
    try:
        d = sa.distToShape(sb)[0]
    except Exception as e:
        d = repr(e)
    out.append({"a": a, "b": b, "common_volume": vol, "common_subshapes": nsub, "common_bbox_valid": bbv, "common_error": err, "dist": d})
result = json.dumps(out)
''' % (pairs,)

def payload(r):
    return r["structured"]

def script_result(r):
    sc = r["structured"]["structured_content"]
    res = sc.get("value_repr")
    return json.loads(ast.literal_eval(res)) if isinstance(res, str) else res

async def main():
    log = []
    created = (await call_many([("document_create", {"label": "Interference137"})]))[0]
    log.append(created)
    doc = created["structured"]["structured_content"]["doc"]
    names = ["A", "Sep", "Over", "FaceTouch", "VertTouch", "Cyl", "Bowtie"]
    explicit = [["A", "Sep"], ["Over", "A"], ["A", "FaceTouch"], ["VertTouch", "A"], ["A", "Cyl"], ["Bowtie", "A"]]
    all_pairs = [[names[i], names[j]] for i in range(len(names)) for j in range(i + 1, len(names))]
    calls = [
        ("script_exec", {"doc": doc, "code": BUILD}),
        ("script_exec", {"doc": doc, "code": STATE}),
        ("query_interference", {"doc": doc, "objects": names}),
        ("query_interference", {"doc": doc, "pairs": explicit}),
        ("script_exec", {"doc": doc, "code": STATE}),
        ("script_exec", {"doc": doc, "code": script_pairs(all_pairs + explicit)}),
        # bad inputs through the bridge
        ("query_interference", {"doc": doc, "pairs": [["A", "A"]]}),
        ("query_interference", {"doc": doc, "objects": ["A", "Nope"]}),
        ("query_interference", {"doc": doc, "objects": names, "pairs": explicit}),
        ("query_interference", {"doc": doc, "objects": [f"X{i}" for i in range(21)]}),
        ("script_exec", {"doc": doc, "code": STATE}),
    ]
    res = await call_many(calls)
    log += res
    json.dump({"doc": doc, "calls": log}, open(OUT + r"\cap1-replay.json", "w"), indent=1, default=str)
    st0, st1, st2 = (script_result(res[i]) for i in (1, 4, 10))
    print("STATE before==after_queries:", st0 == st1, "| ==after_bad_inputs:", st0 == st2, "| digest", st0["digest"][:16], st1["digest"][:16], "undo", st0["undo"], st1["undo"], st2["undo"], "touched", st0["touched"], st1["touched"])
    ref = {(p["a"], p["b"]): p for p in script_result(res[5])}
    for idx in (2, 3):
        r = res[idx]; sc = r["structured"]
        print(f"--- query_interference form={'objects' if 'objects' in r['args'] else 'pairs'} status={sc['status']} elapsed={r['elapsed_s']}s")
        for p in sc["structured_content"]["pairs"]:
            s = ref[(p["a"], p["b"])]
            cv = p["common_volume"]["value"] if p["common_volume"] else None
            md = p["min_distance"]["value"] if p["min_distance"] else None
            vol_match = (cv is None) or (s["common_volume"] is not None and abs(cv - abs(s["common_volume"])) <= 1e-6 * max(1, cv))
            dist_match = (md is None and not isinstance(s["dist"], float)) or (isinstance(s["dist"], float) and md is not None and abs(md - s["dist"]) <= 1e-9) or (cv and md == 0.0)
            print(f"{p['a']:>9}/{p['b']:<9} tool vol={cv!s:>22} dist={md!s:>8} failed={p['boolean_failed']!s:5} | script vol={s['common_volume']!s:>22} subshapes={s['common_subshapes']} dist={s['dist']} err={s['common_error']} | vol_ok={vol_match} dist_ok={dist_match}")
        print("TEXT:", sc["text"].replace("\n", " || "))
    for idx in range(6, 10):
        r = res[idx]; sc = r["structured"]
        print("BAD", json.dumps(r["args"])[:90], "->", r.get("isError"), (sc or {}).get("status"), (sc or {}).get("detail") or r.get("text"))
if __name__ == "__main__":
    asyncio.run(main())
