"""TC-03-14. The Given (an unpinned rectangle with dof>0) cannot exist: every sketch_* mutation is
rolled back unless the sketch ends fully constrained (AD-8). Part A runs the TC as written; part B
judges the -1/-2 operand contract on its merits in a sketch that does end fully constrained."""
from tc03lib import *  # noqa: F401,F403

GEO = [
    {"kind": "line_segment", "start": [10, 10], "end": [70, 10]},
    {"kind": "line_segment", "start": [70, 10], "end": [70, 50]},
    {"kind": "line_segment", "start": [70, 50], "end": [10, 50]},
    {"kind": "line_segment", "start": [10, 50], "end": [10, 10]},
]
SHAPE = [
    {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
    {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
    {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1},
    {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
    {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
    {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
    {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": 60, "unit": "mm"}},
    {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": {"value": 40, "unit": "mm"}},
]
ON_H = {"type": "PointOnObject", "first": 0, "first_pos": 1, "second": -1}
ON_V = {"type": "PointOnObject", "first": 3, "first_pos": 1, "second": -2}


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await m.call("sketch_create", {"doc": doc, "name": "AxisProfile", "plane": "XY"})
    g = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "AxisProfile", "geometry": GEO, "constraints": SHAPE})
    log.note(f"A: Given build (unpinned rectangle, dof 2): {g.get('status')} {json.dumps(g.get('detail'))[:200]}")
    v0 = await m.call("verify_sketch", {"doc": doc, "sketch": "AxisProfile"})
    d0 = (sc(v0).get("subject") or {}).get("dof")
    log.check("A: Given verify_sketch AxisProfile dof > 0", isinstance(d0, int) and d0 > 0,
              f"dof={d0} geometry_count={(sc(v0).get('subject') or {}).get('geometry_count')} (Given rolled back by AD-8)")
    fit0 = await m.fit(doc)
    log.write({"shot": shot("tc-03-14-before.png")})
    a1 = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "AxisProfile", "constraints": [ON_H]})
    a2 = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "AxisProfile", "constraints": [ON_V]})
    log.check("A: -1 call OK rolled_back=false", a1.get("status") == "OK", short(a1))
    log.check("A: -2 call OK rolled_back=false", a2.get("status") == "OK", short(a2))

    # B: merits. The same rectangle in one call, pinned only by the two axis PointOnObject constraints.
    await m.call("sketch_create", {"doc": doc, "name": "AxisProfileB", "plane": "XY"})
    b = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "AxisProfileB", "geometry": GEO, "constraints": SHAPE + [ON_H, ON_V]})
    log.check("B: rectangle pinned by PointOnObject to -1 (HAxis) and -2 (VAxis) commits OK", b.get("status") == "OK" and mut(b).get("rolled_back") is False, short(b))
    vb = await m.call("verify_sketch", {"doc": doc, "sketch": "AxisProfileB"})
    log.check("B: verify dof=0", (sc(vb).get("subject") or {}).get("dof") == 0, short(vb))
    ib = await m.call("query_sketch_info", {"doc": doc, "sketch": "AxisProfileB"})
    poo = [c for c in sc(ib).get("constraints") or [] if c.get("type") == "PointOnObject"]
    log.check("B: both PointOnObject constraints readable with 1-based ids", len(poo) == 2 and all(c.get("id", 0) >= 1 for c in poo), json.dumps(poo))
    # axis as `first`: replace nothing, add a redundant-consistent Coincident(-1 root point, line0 start) would conflict;
    # use a separate sketch whose corner is pinned by Coincident(first=-1)
    await m.call("sketch_create", {"doc": doc, "name": "AxisFirst", "plane": "XY"})
    geo0 = [dict(x) for x in RECT_GEOMETRY]
    shape0 = [c for c in rect_constraints(names=False) if not (c["type"] == "Coincident" and c.get("second") == -1)]
    cf = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "AxisFirst", "geometry": geo0,
        "constraints": shape0 + [{"type": "Coincident", "first": -1, "first_pos": 1, "second": 0, "second_pos": 1}]})
    log.check("axis as first: Coincident(first=-1, first_pos=1, second=0, second_pos=1) accepted", cf.get("status") == "OK", short(cf))
    bad = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "AxisProfileB",
                                                 "constraints": [{"type": "PointOnObject", "first": 0, "first_pos": 1, "second": -9}]})
    log.check("second=-9 INVALID_INPUT", bad.get("status") == "INVALID_INPUT", short(bad))
    await m.call("document_close", {"doc": doc}) if False else None
    fit = await m.fit(doc)
    log.note(f"fit: {fit}")
    log.write({"shot": shot("tc-03-14-after.png")})
    log.write({"edit_B": edit_capture("AxisProfileB", "tc-03-14-edit-B.png")})


go("tc-03-14", body)
