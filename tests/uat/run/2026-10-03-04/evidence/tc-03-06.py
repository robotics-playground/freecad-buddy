"""TC-03-06 as written. The Given names 5 entries (two lines, two circles, a point) but the When
references geo 4 as a line and geo 5 as a point; the Given is built literally (L0 L1 C2 C3 P4),
pinned with one Block per element because sketch_add_geometry must leave the sketch fully
constrained (AD-8)."""
from tc03lib import *  # noqa: F401,F403

GEOMETRY = [
    {"kind": "line_segment", "start": [0, 0], "end": [60, 0]},
    {"kind": "line_segment", "start": [60, 0], "end": [60, 40]},
    {"kind": "circle", "center": [80, 20], "radius": {"value": 2.5, "unit": "mm"}},
    {"kind": "circle", "center": [85, 20], "radius": {"value": 2.5, "unit": "mm"}},
    {"kind": "point", "center": [30, 0]},
]
PINS = [{"type": "Block", "first": i} for i in range(5)]
GEOMETRIC = [
    {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
    {"type": "Horizontal", "first": 0},
    {"type": "Vertical", "first": 1},
    {"type": "Parallel", "first": 0, "second": 4},
    {"type": "Perpendicular", "first": 1, "second": 4},
    {"type": "Tangent", "first": 2, "second": 3},
    {"type": "Equal", "first": 2, "second": 3},
    {"type": "Symmetric", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "third": -2},
    {"type": "PointOnObject", "first": 5, "first_pos": 1, "second": 0},
    {"type": "Block", "first": 4},
]
DIMENSIONAL = [
    {"type": "Distance", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": 60, "unit": "mm"}},
    {"type": "DistanceX", "first": 1, "first_pos": 1, "value": {"value": 60, "unit": "mm"}},
    {"type": "DistanceY", "first": 1, "first_pos": 1, "value": {"value": 0, "unit": "mm"}},
    {"type": "Radius", "first": 2, "value": {"value": 2.5, "unit": "mm"}},
    {"type": "Diameter", "first": 3, "value": {"value": 5, "unit": "mm"}},
    {"type": "Angle", "first": 0, "second": 4, "value": {"value": 45, "unit": "deg"}},
]


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await m.call("sketch_create", {"doc": doc, "name": "ConstraintBed", "plane": "XY"})
    gv = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "ConstraintBed", "geometry": GEOMETRY, "constraints": PINS})
    log.note(f"Given build (5 elements, 5 Block pins): {gv.get('status')} {json.dumps(gv.get('detail'))[:200]}")
    g = await m.call("query_sketch_info", {"doc": doc, "sketch": "ConstraintBed"})
    log.check("Given ConstraintBed reports 5 geometry entries", len(sc(g).get("geometry") or []) == 5,
              f"count={len(sc(g).get('geometry') or [])} types={[x.get('type') for x in sc(g).get('geometry') or []]}")
    before_ids = [c.get("id") for c in sc(g).get("constraints") or []]

    c1 = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "ConstraintBed", "constraints": GEOMETRIC})
    c2 = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "ConstraintBed", "constraints": DIMENSIONAL})
    log.check("both calls return OK covering all 16 types", c1.get("status") == "OK" and c2.get("status") == "OK",
              f"call1={short(c1, 250)} || call2={short(c2, 250)}")
    ids1 = sc(c1).get("constraint_ids")
    log.check("first call's lowest returned constraint id is 1", bool(ids1) and min(ids1) == 1, f"constraint_ids={ids1} (Given pins hold ids {before_ids})")
    info = await m.call("query_sketch_info", {"doc": doc, "sketch": "ConstraintBed"})
    ids = [c.get("id") for c in sc(info).get("constraints") or []]
    log.check("read back ids run 1..16, no id=0", ids == list(range(1, 17)), f"ids={ids}")
    cons = sc(info).get("constraints") or []
    rad = [c.get("value") for c in cons if c.get("type") == "Radius"]
    ang = [c.get("value") for c in cons if c.get("type") == "Angle"]
    log.check("Radius reads {2.5 mm} and Angle reads {45 deg}", {"value": 2.5, "unit": "mm"} in rad and {"value": 45.0, "unit": "deg"} in ang,
              f"radius={rad} angle={ang}")
    r = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "ConstraintBed", "constraints": [{"type": "Symmetry", "first": 0}]})
    log.check("type Symmetry is a schema reject", schema_reject(r), short(r))
    r = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "ConstraintBed", "constraints": [{"type": "Horizontal"}]})
    log.check("missing first is a schema reject", schema_reject(r), short(r))
    r = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "ConstraintBed",
                                                "constraints": [{"type": "Horizontal", "first": 0, "first_pos": 4}]})
    log.check("first_pos 4 is a schema reject", schema_reject(r), short(r))
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "ConstraintBed"})
    subj = sc(v).get("subject") or {}
    log.check("verify_sketch graded with constraint_count=16", subj.get("constraint_count") == 16,
              f"status={v.get('status')} constraint_count={subj.get('constraint_count')} dof={subj.get('dof')}")
    fit = await m.fit(doc)
    log.note(f"fit: {fit}")
    log.write({"shot": shot("tc-03-06-after.png")})
    log.write({"edit": edit_capture("ConstraintBed", "tc-03-06-edit-ConstraintBed.png")})


go("tc-03-06", body)
