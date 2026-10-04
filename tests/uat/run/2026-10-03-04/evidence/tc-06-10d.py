"""TC-06-10 second attempt: render immediately after the property-editor edit (no verify_recompute, which recomputes: verify.py:411)."""
from tc06lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0610"][0]
    r1, p1 = await render(m, doc, {"camera": "iso"}, "tc-06-10-dirty2.png")
    log.note(f"render right after GUI edit: render={sc(r1).get('render')} text={(r1.get('text') or '')[:80]!r}")
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "BoxPad"})
    log.note(f"BoxPad volume now (30 mm pad -> 6000, 25 -> 5000): {sc(mp).get('volume')}")

go("tc-06-10d", body)
