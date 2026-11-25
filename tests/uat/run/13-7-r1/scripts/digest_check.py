import ast, asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcpcall import call_many
import replay
OUT = replay.OUT
FP = '''
import json
from freecad_buddy.usecases.fingerprint import fingerprint
r = fingerprint(doc, fresh=True)
result = json.dumps({"digest": r["digest"], "objects": {o["name"]: [o["brep_sha256"][:12], o["massprops"]] for o in r["objects"]}})
'''
def val(r):
    return json.loads(ast.literal_eval(r["structured"]["structured_content"]["value_repr"]))
async def main():
    docs = (await call_many([("document_list", {})]))[0]["structured"]["structured_content"]["documents"]
    await call_many([("document_close", {"doc": d["doc"]}) for d in docs])
    doc = (await call_many([("document_create", {"label": "Digest137"})]))[0]["structured"]["structured_content"]["doc"]
    names = ["A", "Sep", "Over", "FaceTouch", "VertTouch", "Cyl", "Bowtie"]
    res = await call_many([("script_exec", {"doc": doc, "code": replay.BUILD}),
        ("script_exec", {"doc": doc, "code": FP}), ("script_exec", {"doc": doc, "code": FP}),
        ("script_exec", {"doc": doc, "code": FP}),
        ("query_interference", {"doc": doc, "objects": names}),
        ("script_exec", {"doc": doc, "code": FP}),
        ("query_interference", {"doc": doc, "pairs": [["Bowtie", "A"], ["A", "Cyl"]]}),
        ("script_exec", {"doc": doc, "code": FP})])
    fps = [val(res[i]) for i in (1, 2, 3, 5, 7)]
    labels = ["after_build_1", "control_2", "control_3", "after_objects_query", "after_pairs_query"]
    for l, f in zip(labels, fps):
        print(l, f["digest"][:16])
    a, b = fps[0], fps[2]
    for n in a["objects"]:
        if a["objects"][n] != b["objects"][n]:
            print("DIFF", n, a["objects"][n][0], b["objects"][n][0], a["objects"][n][1] == b["objects"][n][1])
    json.dump({"doc": doc, "labels": labels, "fingerprints": fps, "calls": res}, open(OUT + r"\digest-check.json", "w"), indent=1, default=str)
asyncio.run(main())
