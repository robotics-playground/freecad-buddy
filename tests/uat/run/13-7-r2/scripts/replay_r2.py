"""Round 2 CAP-1 replay: trusted pairs equal the script; untrusted pairs read boolean_failed with null numbers."""
import ast, asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcpcall import call_many
import replay
OUT = r"D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-7-r2"
EXTRA = '''
import Part, FreeCAD as App
V = App.Vector
src = doc.addObject("Part::Feature", "RevSrc"); src.Shape = Part.makeBox(10, 10, 10, V(40, 0, 0))
rev = doc.addObject("Part::Reverse", "Reversed"); rev.Source = src
inner = doc.addObject("Part::Feature", "InRev"); inner.Shape = Part.makeBox(2, 2, 2, V(44, 4, 4))
sh = doc.addObject("Part::Feature", "Shell"); sh.Shape = Part.makeBox(50, 50, 50, V(-20, -20, -20)).Shells[0]
doc.recompute()
result = [doc.Reversed.Shape.Volume, doc.Shell.Shape.ShapeType, doc.Bowtie.Shape.isValid()]
'''
FP = '''
import json
from freecad_buddy.usecases.fingerprint import fingerprint
result = json.dumps({"fresh": fingerprint(doc, fresh=True)["digest"], "cached": fingerprint(doc)["digest"], "undo": doc.UndoCount, "touched": [o.Name for o in doc.Objects if "Touched" in o.State]})
'''
TRUST = '''
import json
def ok(s):
    def vols(x):
        if x.ShapeType == "Solid": return [x.Volume]
        if x.ShapeType in ("Compound", "CompSolid"): return [v for c in x.SubShapes for v in vols(c)]
        return [None]
    v = vols(s); return bool(v) and all(a is not None and a > 0 for a in v) and s.isValid()
result = json.dumps({o.Name: ok(o.Shape) for o in doc.Objects if o.Name in %r})
'''
def val(r):
    return json.loads(ast.literal_eval(r["structured"]["structured_content"]["value_repr"]))
async def main():
    os.makedirs(OUT, exist_ok=True)
    docs = (await call_many([("document_list", {})]))[0]["structured"]["structured_content"]["documents"]
    await call_many([("document_close", {"doc": d["doc"]}) for d in docs])
    doc = (await call_many([("document_create", {"label": "Interference137r2"})]))[0]["structured"]["structured_content"]["doc"]
    names = ["A", "Sep", "Over", "FaceTouch", "VertTouch", "Cyl", "Bowtie", "Reversed", "InRev", "Shell"]
    explicit = [["A", "Sep"], ["Over", "A"], ["A", "FaceTouch"], ["Bowtie", "A"], ["Reversed", "InRev"], ["Shell", "A"], ["A", "Cyl"]]
    allp = [[names[i], names[j]] for i in range(len(names)) for j in range(i + 1, len(names))]
    res = await call_many([
        ("script_exec", {"doc": doc, "code": replay.BUILD}), ("script_exec", {"doc": doc, "code": EXTRA}),
        ("script_exec", {"doc": doc, "code": FP}),
        ("query_interference", {"doc": doc, "objects": names}),
        ("query_interference", {"doc": doc, "pairs": explicit}),
        ("script_exec", {"doc": doc, "code": FP}),
        ("script_exec", {"doc": doc, "code": replay.script_pairs(allp + explicit)}),
        ("script_exec", {"doc": doc, "code": TRUST % (names,)}),
        ("view_fit_viewport", {"doc": doc})])
    print("extra:", res[1]["structured"]["structured_content"]["value_repr"])
    f0, f1 = val(res[2]), val(res[5])
    print(f"fingerprint fresh equal={f0['fresh'] == f1['fresh']} cached equal={f0['cached'] == f1['cached']} undo {f0['undo']}->{f1['undo']} touched {f0['touched']}->{f1['touched']}")
    ref = {(p["a"], p["b"]): p for p in val(res[6])}
    trust = val(res[7]); print("trusted:", trust)
    bad = 0; n = 0
    for idx in (3, 4):
        sc = res[idx]["structured"]
        print(f"--- form={'objects' if 'objects' in res[idx]['args'] else 'pairs'} status={sc['status']} elapsed={res[idx]['elapsed_s']}s")
        for p in sc["structured_content"]["pairs"]:
            n += 1; s = ref[(p["a"], p["b"])]
            cv = (p["common_volume"] or {}).get("value"); md = (p["min_distance"] or {}).get("value")
            if trust[p["a"]] and trust[p["b"]]:
                if p["boolean_failed"]:
                    ok = cv is None and s["common_volume"] in (0.0, None) and s["dist"] == 0.0  # touching rule
                else:
                    ok = abs(cv - s["common_volume"]) <= 0.005 + 1e-6 * abs(s["common_volume"]) and (cv > 0 and md == 0.0 or abs(md - s["dist"]) <= 0.005)
                kind = "trusted"
            else:
                ok = p["boolean_failed"] and cv is None and md is None; kind = "untrusted"
            bad += not ok
            print(f"{p['a']:>9}/{p['b']:<9} {kind:9} tool vol={cv!s:>8} dist={md!s:>6} failed={p['boolean_failed']!s:5} | script vol={s['common_volume']!s:>20} dist={s['dist']} | ok={ok}")
        print("TEXT:", sc["text"].split("\n\n")[0].replace("\n", " || "))
    print(f"RESULT records={n} mismatches={bad}")
    json.dump({"doc": doc, "calls": res}, open(OUT + r"\cap1-replay.json", "w"), indent=1, default=str)
asyncio.run(main())
