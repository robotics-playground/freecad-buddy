import sys, json
from tc03lib import *
async def body(m, log):
    docs = await m.call("document_list", {})
    for d in (sc(docs).get("documents") or []):
        h = d.get("doc") or d.get("handle")
        r = await m.call("document_close", {"doc": h})
        log.note(f"document_close {d.get('label')} -> {r.get('status')}")
go(sys.argv[1] + "-cleanup", body)
