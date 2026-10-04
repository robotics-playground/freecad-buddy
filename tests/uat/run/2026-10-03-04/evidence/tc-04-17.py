from tc04lib import *  # noqa: F401,F403


async def shaft(m, label):
    h = sc(await m.call("document_create", {"label": label})).get("doc")
    await m.call("feature_body_create", {"doc": h, "name": "ShaftBody"})
    await sketch(m, h, "ShaftProfile", "ShaftBody", rect_profile(0, 0, 5, 20), plane="XZ")
    await m.call("feature_revolve", {"doc": h, "body": "ShaftBody", "profile": "ShaftProfile", "name": "ShaftRev",
                                     "axis": sel("ShaftProfile", "V_Axis"), "angle": q(360, "deg")})
    return h


async def body(m, log):
    log.note("Outside oracle (tc-04-topology-oracle.txt): ShaftRev Edge1/Edge2 are the bottom/top circles (sharp plane-cylinder creases), "
             "Edge3 is the cylinder seam line (the cylindrical face meets itself). The TC's 'Edge2' is not the seam; the seam is Edge3.")
    h = await shaft(m, "SeamFillet")
    v0 = await m.call("query_mass_properties", {"doc": h, "object": "ShaftRev"})
    log.check("Given ShaftRev exists (query_object lists properties only; seam identified by oracle)", near(vol(v0), 1570.7963), vol(v0))
    base = snaps()
    await capture(m, h, "tc-04-17-before.png")
    s1 = await m.call("feature_fillet", {"doc": h, "body": "ShaftBody", "base": "ShaftRev", "name": "DropFillet",
                                         "edges": [sel("ShaftRev", "Edge3")], "radius": q(1)})
    s2 = await m.call("feature_fillet", {"doc": h, "body": "ShaftBody", "base": "ShaftRev", "name": "MixedFillet",
                                         "edges": [sel("ShaftRev", "Edge1"), sel("ShaftRev", "Edge3")], "radius": q(1)})
    msg = detail_msg(s1)
    log.check("step 1 INVALID_INPUT 'cannot be shown to survive the dress-up' listing the edge",
              s1.get("status") == "INVALID_INPUT" and "cannot be shown to survive the dress-up" in msg and "Edge3" in msg, msg[:400])
    log.check("reason stated", "each needs exactly two adjacent faces meeting at a measurable crease, and FreeCAD drops the rest without reporting it" in msg, msg[:400])
    log.check("pre-transaction: no snapshot_path, no new snapshot dir", not mut(s1).get("snapshot_path") and set(snaps()) == set(base), "")
    log.check("mixed request refused whole", s2.get("status") == "INVALID_INPUT", short(s2, 300))
    tr = await m.call("query_tree_summary", {"doc": h, "depth": 3})
    log.check("tree names neither DropFillet nor MixedFillet", "DropFillet" not in tree_names(tr) and "MixedFillet" not in tree_names(tr), "")
    v1 = await m.call("query_mass_properties", {"doc": h, "object": "ShaftRev"})
    log.check("ShaftRev volume unchanged", vol(v1) == vol(v0), f"{vol(v0)} -> {vol(v1)}")
    log.check("committed under-dressed fillet caught as SPEC_FAILED 'dressed N of the M requested edge(s)'", None,
              "NOT RUN: no input found that commits a dress-up which drops an edge - the up-front check refuses every droppable edge tried")
    hc = await shaft(m, "SeamFilletLiteral")
    lit = await m.call("feature_fillet", {"doc": hc, "body": "ShaftBody", "base": "ShaftRev", "name": "DropFillet",
                                          "edges": [sel("ShaftRev", "Edge2")], "radius": q(1)})
    log.note(f"literal Edge2 (top circle) on a copy -> {short(lit, 300)} summary={json.dumps(ss(lit))}")
    await m.call("document_close", {"doc": hc})
    await capture(m, h, "tc-04-17-after.png")
    log.write({"doc": h})


go("tc-04-17", body)
