"""Near-limit dense pair and the 40 s deadline through the bridge."""
import asyncio, json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcpcall import call_many
OUT2 = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/13-7-r2"
N = 63  # 63 boxes x 6 faces = 378 faces; 378 * 378 = 142,884 <= 150,000
DENSE = '''
import Part, FreeCAD as App
V = App.Vector
for name, dx in (("D1", 0.0), ("D2", 5.0)):
    boxes = [Part.makeBox(4, 4, 4, V(dx + 10 * (k %% 9), 10 * (k // 9), 0)) for k in range(%d)]
    o = doc.addObject("Part::Feature", name); o.Shape = Part.makeCompound(boxes)
result = [len(doc.D1.Shape.Faces), len(doc.D2.Shape.Faces)]
''' % N
async def main():
    docs = (await call_many([("document_list", {})]))[0]["structured"]["structured_content"]["documents"]
    await call_many([("document_close", {"doc": d["doc"]}) for d in docs])
    doc = (await call_many([("document_create", {"label": "Limit137"})]))[0]["structured"]["structured_content"]["doc"]
    b = (await call_many([("script_exec", {"doc": doc, "code": DENSE})]))[0]
    print("faces", b["structured"]["structured_content"]["value_repr"])
    one = (await call_many([("query_interference", {"doc": doc, "pairs": [["D1", "D2"]]})]))[0]
    sc = one["structured"]
    print(f"one near-limit pair: status={sc['status']} elapsed={one['elapsed_s']}s content={json.dumps(sc.get('structured_content'))[:200]}")
    many = (await call_many([("query_interference", {"doc": doc, "pairs": [["D1", "D2"]] * 8})]))[0]
    sc = many["structured"]
    print(f"8 near-limit pairs: status={sc['status']} elapsed={many['elapsed_s']}s detail={sc.get('detail')}")
    after = (await call_many([("query_interference", {"doc": doc, "pairs": [["D1", "D2"]]})]))[0]
    print(f"call right after: status={after['structured']['status']} elapsed={after['elapsed_s']}s")
    json.dump({"one": one, "many": many, "after": after}, open(OUT2 + "/limit-deadline.json", "w"), indent=1, default=str)
asyncio.run(main())
