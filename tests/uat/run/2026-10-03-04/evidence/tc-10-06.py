"""TC-10-06 When/Then: A opens a document; B (fresh hello) uses A's handle verbatim."""
import json
from tc10lib import CYL, Log, Rpc
log = Log("tc-10-06.jsonl")
out = {}
a = Rpc(log, "06", "A"); a.hello()
o = a.call("document_open", {"path": CYL})
ha = (o.get("structured_content") or {}).get("doc")
out["A_open"] = {"status": o.get("status"), "handle": ha}
tree = a.call("query_tree_summary", {"doc": ha})["structured_content"]["tree"]
obj = tree[0]["name"]; out["object"] = obj
a.close()
b = Rpc(log, "06", "B"); out["B_hello"] = "result" in (b.hello() or {})
q = b.call("query_object", {"doc": ha, "object": obj})
out["B_query_object_with_A_handle"] = {"status": q.get("status"), "schema": q.get("schema"),
                                       "detail": q.get("detail"), "has_properties": bool((q.get("structured_content") or {}))}
dl = b.call("document_list", {})
docs = dl["structured_content"]["documents"]
out["B_document_list"] = {"status": dl.get("status"), "handles": [d["doc"] for d in docs], "contains_A_handle": ha in [d["doc"] for d in docs]}
out["B_followup_document_list"] = b.call("document_list", {}).get("status")
b.close()
print(json.dumps(out, indent=1)); open("tc-10-06-checks.json", "w").write(json.dumps(out, indent=1))
