"""Probe: at which nesting depth does the H2 proxy stop delivering verify_shape checks to the handler?"""
import json

from tc09lib import EV, raw_call, sc
from tc09lib import Log

log = Log("tc-09-10-depthprobe")
docs = sc(raw_call("document_list", {})).get("documents") or []
doc = docs[0]["doc"]


def nest(depth):
    node = {"a": 1}
    for _ in range(depth - 1):
        node = {"a": node}
    return node


for depth in (10, 50, 80, 90, 95, 100):
    e = raw_call("verify_shape", {"doc": doc, "object": "Box", "checks": [{"fn": nest(depth)}]}, log)
    d = e.get("detail") or {}
    print(depth, e.get("status"), (d.get("message") or "")[:60] if isinstance(d, dict) else "", e.get("_rpcerr"))
