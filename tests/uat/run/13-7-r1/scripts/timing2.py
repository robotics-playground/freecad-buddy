import ast, asyncio, json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcpcall import call_many
import replay
N = int(sys.argv[1]); TAG = sys.argv[2]
COMP = '''
import Part, FreeCAD as App
V = App.Vector
for name, off in (("C1", 0.0), ("C2", 5000.0)):
    boxes = [Part.makeBox(4, 4, 4, V(off + 10 * (k %% 20), 10 * (k // 20), 0)) for k in range(%d)]
    o = doc.addObject("Part::Feature", name); o.Shape = Part.makeCompound(boxes)
o = doc.addObject("Part::Feature", "P"); o.Shape = Part.makeBox(1, 1, 1, V(0, 0, 100))
o = doc.addObject("Part::Feature", "Q"); o.Shape = Part.makeBox(1, 1, 1, V(5, 0, 100))
result = len(doc.Objects)
''' % N
FP = '''
import json
from freecad_buddy.usecases.fingerprint import fingerprint
result = json.dumps({"cached": fingerprint(doc)["digest"], "touched": [o.Name for o in doc.Objects if "Touched" in o.State or "Invalid" in o.State], "undo": doc.UndoCount, "n": len(doc.Objects)})
'''
def health():
    try:
        return urllib.request.urlopen("http://127.0.0.1:18765/healthz", timeout=5).read().decode()
    except Exception as e:
        return repr(e)
async def main():
    docs = (await call_many([("document_list", {})]))[0]["structured"]["structured_content"]["documents"]
    await call_many([("document_close", {"doc": d["doc"]}) for d in docs])
    doc = (await call_many([("document_create", {"label": "Compound137"})]))[0]["structured"]["structured_content"]["doc"]
    b = await call_many([("script_exec", {"doc": doc, "code": COMP}), ("script_exec", {"doc": doc, "code": FP})])
    print("build", b[0]["structured"]["status"], b[0]["elapsed_s"], "state", b[1]["structured"]["structured_content"]["value_repr"][:120])
    t0 = time.monotonic()
    r = (await call_many([("query_interference", {"doc": doc, "pairs": [["C1", "C2"]]})]))[0]
    sc = r["structured"] or {}
    print(f"compound pair N={N}: status={sc.get('status')} elapsed={r['elapsed_s']}s isError={r.get('isError')} exc={r.get('exception')} detail={str(sc.get('detail'))[:400]} content={json.dumps(sc.get('structured_content'))[:300]} text={str(r.get('text'))[:300]}")
    print("health right after:", health())
    t1 = time.monotonic()
    after = await call_many([("query_interference", {"doc": doc, "pairs": [["P", "Q"]]}), ("script_exec", {"doc": doc, "code": FP}), ("document_list", {})])
    print(f"follow-up small query: status={(after[0]['structured'] or {}).get('status')} elapsed={after[0]['elapsed_s']}s (started {round(t1 - t0, 1)} s after the big call began) detail={str((after[0]['structured'] or {}).get('detail'))[:200]}")
    print("state after:", after[1]["elapsed_s"], (after[1]["structured"] or {}).get("status"), str((after[1]["structured"] or {}).get("structured_content", {}).get("value_repr"))[:160])
    print("document_list:", json.dumps((after[2]["structured"] or {}).get("structured_content"))[:300])
    json.dump({"N": N, "build": b, "big": r, "after": after, "health": health()}, open(replay.OUT + rf"\timing-compound-{TAG}.json", "w"), indent=1, default=str)
asyncio.run(main())
