from tc05lib import *

LOOSE = ("import Part, Sketcher\n"
         "b = doc.getObject('Body')\n"
         "xy = [f for f in b.Origin.OriginFeatures if f.Role == 'XY_Plane'][0]\n"
         "s = b.newObject('Sketcher::SketchObject', 'Loose')\n"
         "s.AttachmentSupport = [(xy, '')]\n"
         "s.MapMode = 'FlatFace'\n"
         "P = FreeCAD.Vector\n"
         "pts = [P(5,5,0), P(15,5,0), P(15,15,0), P(5,15,0)]\n"
         "for i in range(4):\n"
         "    s.addGeometry(Part.LineSegment(pts[i], pts[(i+1)%4]))\n"
         "for i in range(4):\n"
         "    s.addConstraint(Sketcher.Constraint('Coincident', i, 2, (i+1)%4, 1))\n"
         "s.addConstraint(Sketcher.Constraint('Horizontal', 0)); s.addConstraint(Sketcher.Constraint('Horizontal', 2))\n"
         "s.addConstraint(Sketcher.Constraint('Vertical', 1)); s.addConstraint(Sketcher.Constraint('Vertical', 3))\n"
         "doc.recompute()\n"
         "result = (s.Name, s.solve(), s.ConstraintCount)")
GOOD = {"body": "Body", "base": "Pad", "name": "GoodFillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)}


async def good_then_undo(m, log, doc, tag, base_snaps):
    p, g = await apply(m, doc, "feature_fillet", GOOD)
    mb = mut(g)
    log.check(f"[{tag}] GoodFillet status OK", g.get("status") == "OK", short(g))
    log.check(f"[{tag}] GoodFillet transaction_id '0'", mb.get("transaction_id") == "0", mb.get("transaction_id"))
    log.check(f"[{tag}] no snapshot leaked", set(run_snaps()) - base_snaps == set(), sorted(set(run_snaps()) - base_snaps))
    u = await m.call("document_undo", {"doc": doc})
    msg = (u.get("detail") or {}).get("message") if isinstance(u.get("detail"), dict) else ""
    log.check(f"[{tag}] document_undo NOT refused 'has an open transaction; undo would commit it'", "has an open transaction" not in str(msg) and u.get("status") == "OK", short(u))
    undone = sc(u).get("undone")
    log.check(f"[{tag}] undone == 'buddy: <follow-up label>' (GoodFillet)", isinstance(undone, str) and undone.startswith("buddy: ") and "fillet" in undone.lower(), undone)
    return g


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0509", pad=30)
    pm = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("Given Pad volume 12000.0", near(vol(pm), 12000.0, 1e-6), vol(pm))
    base = set(run_snaps())
    # path 1: under-constrained sketch (fixture sketch built in-process: MCP cannot leave dof>0)
    lx = await m.call("debug_exec", {"doc": doc, "code": LOOSE})
    log.note(f"fixture Loose sketch (dof>0) via debug_exec -> {short(lx)} {sc(lx).get('value_repr')}")
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "Loose"})
    log.note(f"verify_sketch Loose -> status={v.get('status')} dof={(sc(v).get('subject') or {}).get('dof')}")
    p1, f1 = await apply(m, doc, "feature_pad", {"body": "Body", "profile": "Loose", "name": "LoosePad", "length": q(10)})
    log.note(f"path1 under-constrained pad -> status={f1.get('status')} rolled_back={mut(f1).get('rolled_back')} expl={pv(f1).get('explanation')}")
    if f1.get("status") == "OK":
        u = await m.call("document_undo", {"doc": doc})
        log.note(f"path1 COMMITTED (known defect: profile sketch not graded); undid it to restore the fixture -> {short(u)} undone={sc(u).get('undone')}")
    await good_then_undo(m, log, doc, "after under-constrained", base)
    # path 2: impossible fillet
    p2, f2 = await apply(m, doc, "feature_fillet", dict(GOOD, name="BadFillet", radius=q(500)))
    log.note(f"path2 impossible fillet -> status={f2.get('status')} proof={mut(f2).get('rollback_proven')}")
    await good_then_undo(m, log, doc, "after impossible fillet", base)
    # path 3: missing base
    p3, f3 = await apply(m, doc, "feature_fillet", dict(GOOD, name="MissingBase", base="NoSuchPad", edges=[sel("NoSuchPad", "Edge1")]))
    log.note(f"path3 missing base -> preview={short(p3)} apply={short(f3)}")
    if f3.get("status") == "NO_TOKEN":
        f3b = await m.call("feature_fillet", dict(GOOD, doc=doc, name="MissingBase", base="NoSuchPad", edges=[sel("NoSuchPad", "Edge1")]))
        log.note(f"path3 apply without a token -> {short(f3b)}")
    g = await good_then_undo(m, log, doc, "after missing base", base)
    # leave the final follow-up applied for the visual: re-apply GoodFillet
    p4, g4 = await apply(m, doc, "feature_fillet", GOOD)
    log.check("final GoodFillet re-applied OK for the visual", g4.get("status") == "OK", short(g4))
    log.check("no snapshot after the successful follow-up", set(run_snaps()) - base == set(), sorted(set(run_snaps()) - base))
    fit, rec = await capture(m, doc, "tc-05-09-after.png")
    log.note(f"after fit={fit}")


go("tc-05-09", body)
