"""Repro: the same 15 constraints (2 redundant) fail in one sketch_add_geometry call but pass incrementally."""
import importlib.util
from tc03lib import *
src = open("tc-03-05-origin.py", encoding="utf-8").read().split("async def body")[0].replace("from tc03lib import *  # noqa: F401,F403", "")
ns = {}
exec(src, ns)
ALL = ns["CONSTRAINTS"]  # TC order, origin form, all 15
async def body(m, log):
    for attempt in (1, 2):
        doc = await new_doc(m, f"Repro{attempt}")
        await m.call("sketch_create", {"doc": doc, "name": "MixedProfile", "plane": "XY"})
        e = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "MixedProfile", "geometry": ns["GEOMETRY"], "constraints": ALL})
        log.note(f"one call, 15 constraints (attempt {attempt}): {e.get('status')} {json.dumps(e.get('detail'))[:200]}")
        await m.call("document_close", {"doc": doc})
go("tc-03-05-repro-tcorder", body)
