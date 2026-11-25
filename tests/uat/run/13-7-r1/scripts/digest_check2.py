import ast, asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcpcall import call_many
import replay
FP = '''
import json
from freecad_buddy.usecases.fingerprint import fingerprint
result = json.dumps({"cached": fingerprint(doc)["digest"], "fresh": fingerprint(doc, fresh=True)["digest"]})
'''
def val(r):
    return json.loads(ast.literal_eval(r["structured"]["structured_content"]["value_repr"]))
async def main():
    docs = (await call_many([("document_list", {})]))[0]["structured"]["structured_content"]["documents"]
    await call_many([("document_close", {"doc": d["doc"]}) for d in docs])
    out = {}
    for label, query in [("query_interference", lambda d: ("query_interference", {"doc": d, "pairs": [["A", "Sep"]]})),
                         ("query_mass_properties", lambda d: ("query_mass_properties", {"doc": d, "objects": ["A", "Sep"]})),
                         ("verify_shape", lambda d: ("verify_shape", {"doc": d, "object": "A", "checks": [{"kind": "is_valid_solid"}]}))]:
        doc = (await call_many([("document_create", {"label": "Fp" + label.replace("_", "")})]))[0]["structured"]["structured_content"]["doc"]
        res = await call_many([("script_exec", {"doc": doc, "code": replay.BUILD}), ("script_exec", {"doc": doc, "code": FP}), query(doc), ("script_exec", {"doc": doc, "code": FP})])
        b, a = val(res[1]), val(res[3])
        q = res[2]["structured"] or {}
        print(f"{label:22} status={q.get('status')} cached_equal={b['cached'] == a['cached']} fresh_equal={b['fresh'] == a['fresh']} detail={str(q.get('detail'))[:120] if q.get('status') != 'OK' else ''}")
        out[label] = {"before": b, "after": a, "query": res[2]}
        await call_many([("document_close", {"doc": doc})])
    json.dump(out, open(replay.OUT + r"\digest-check2.json", "w"), indent=1, default=str)
asyncio.run(main())
