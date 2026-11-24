import ast, asyncio, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcpcall import call_many
import replay
PLATES = '''
import Part, FreeCAD as App
V = App.Vector
for i in range(%d, %d):
    x = i * %f
    holes = Part.makeCompound([Part.makeCylinder(1.5, 5, V(x + 5 + 10 * c, 5 + 10 * r, 0)) for r in range(9) for c in range(9)])
    o = doc.addObject("Part::Feature", "%s%%d" %% i); o.Shape = Part.makeBox(90, 90, 5, V(x, 0, 0)).cut(holes)
result = len(doc.Objects)
'''
FP = '''
import json
from freecad_buddy.usecases.fingerprint import fingerprint
result = json.dumps({"fresh": fingerprint(doc, fresh=True)["digest"], "touched": [o.Name for o in doc.Objects if "Touched" in o.State or "Invalid" in o.State], "undo": doc.UndoCount, "n": len(doc.Objects)})
'''
async def main():
    docs = (await call_many([("document_list", {})]))[0]["structured"]["structured_content"]["documents"]
    await call_many([("document_close", {"doc": d["doc"]}) for d in docs])
    doc = (await call_many([("document_create", {"label": "Timing137"})]))[0]["structured"]["structured_content"]["doc"]
    log = {}
    # overlapping: 90 mm plates every 60 mm -> neighbours overlap; disjoint: every 100 mm
    for prefix, step in (("Ov", 60.0), ("Dj", 100.0)):
        build = [("script_exec", {"doc": doc, "code": PLATES % (k, k + 5, step, prefix)}) for k in (0, 5, 10, 15)]
        b = await call_many(build)
        print(prefix, "build", [r["structured"]["status"] for r in b], [r["elapsed_s"] for r in b])
        names = [f"{prefix}{i}" for i in range(20)]
        r = (await call_many([("query_interference", {"doc": doc, "objects": names})]))[0]
        sc = r["structured"]
        pairs = sc["structured_content"]["pairs"] if sc.get("status") == "OK" else []
        print(f"{prefix} 190 pairs: status={sc.get('status')} elapsed={r['elapsed_s']}s records={len(pairs)} overlapping={sum(1 for p in pairs if (p['common_volume'] or {}).get('value'))} failed={sum(p['boolean_failed'] for p in pairs)}")
        log[prefix] = {"query": r}
    json.dump(log, open(replay.OUT + r"\timing-plates.json", "w"), indent=1, default=str)
asyncio.run(main())
