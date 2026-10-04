"""Repro: the same 15 constraints (2 redundant) fail in one sketch_add_geometry call but pass incrementally."""
import importlib.util
from tc03lib import *
spec = importlib.util.spec_from_file_location("v", "tc-03-05-final.py")
src = open("tc-03-05-final.py", encoding="utf-8").read().split("async def body")[0].replace("from tc03lib import *  # noqa: F401,F403", "")
ns = {}
exec(src, ns)
ALL = ns["CONSTRAINTS"] + ns["ARC_END_CONSTRAINTS"]
async def body(m, log):
    for attempt in (1, 2):
        doc = await new_doc(m, f"Repro{attempt}")
        await m.call("sketch_create", {"doc": doc, "name": "MixedProfile", "plane": "XY"})
        e = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "MixedProfile", "geometry": ns["GEOMETRY"], "constraints": ALL})
        log.note(f"one call, 15 constraints (attempt {attempt}): {e.get('status')} {json.dumps(e.get('detail'))[:200]}")
        await m.call("document_close", {"doc": doc})
    doc = await new_doc(m, "Repro3")
    await m.call("sketch_create", {"doc": doc, "name": "MixedProfile", "plane": "XY"})
    e1 = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "MixedProfile", "geometry": ns["GEOMETRY"], "constraints": ns["CONSTRAINTS"]})
    e2 = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "MixedProfile", "constraints": ns["ARC_END_CONSTRAINTS"]})
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "MixedProfile"})
    log.note(f"13 then +2: {e1.get('status')} / {e2.get('status')}; verify {v.get('status')} redundant={(sc(v).get('subject') or {}).get('redundant')} warnings={json.dumps(sc(v).get('warnings') or v.get('warnings'))[:200]}")
    await m.call("document_close", {"doc": doc})
go("tc-03-05-repro", body)
