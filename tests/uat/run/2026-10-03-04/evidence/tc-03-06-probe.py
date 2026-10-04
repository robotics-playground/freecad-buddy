"""Supplementary probe for TC-03-06 (TC data is self-contradictory): each of the 16 types sent
alone through sketch_add_constraint against a Block-pinned bed whose geometry already satisfies it.
Accepted = the use case built the constraint (status is not INVALID_INPUT)."""
from tc03lib import *  # noqa: F401,F403

GEOMETRY = [
    {"kind": "line_segment", "start": [0, 0], "end": [60, 0]},
    {"kind": "line_segment", "start": [60, 0], "end": [60, 40]},
    {"kind": "circle", "center": [80, 20], "radius": {"value": 2.5, "unit": "mm"}},
    {"kind": "circle", "center": [85, 20], "radius": {"value": 2.5, "unit": "mm"}},
    {"kind": "line_segment", "start": [0, 10], "end": [60, 10]},
    {"kind": "point", "center": [30, 0]},
]
PINS = [{"type": "Block", "first": i} for i in range(6)]
PROBES = [
    {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
    {"type": "Horizontal", "first": 0},
    {"type": "Vertical", "first": 1},
    {"type": "Parallel", "first": 0, "second": 4},
    {"type": "Perpendicular", "first": 1, "second": 4},
    {"type": "Tangent", "first": 2, "second": 3},
    {"type": "Equal", "first": 2, "second": 3},
    {"type": "Symmetric", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "third": 5, "third_pos": 1},
    {"type": "PointOnObject", "first": 5, "first_pos": 1, "second": 0},
    {"type": "Block", "first": 4},
    {"type": "Distance", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": 60, "unit": "mm"}},
    {"type": "DistanceX", "first": -1, "first_pos": 1, "second": 1, "second_pos": 1, "value": {"value": 60, "unit": "mm"}},
    {"type": "DistanceY", "first": -1, "first_pos": 1, "second": 1, "second_pos": 1, "value": {"value": 0, "unit": "mm"}},
    {"type": "Radius", "first": 2, "value": {"value": 2.5, "unit": "mm"}},
    {"type": "Diameter", "first": 3, "value": {"value": 5, "unit": "mm"}},
    {"type": "Angle", "first": 0, "second": 1, "value": {"value": 90, "unit": "deg"}},
]


async def body(m, log):
    doc = await new_doc(m, "ConstraintProbe")
    await m.call("sketch_create", {"doc": doc, "name": "ProbeBed", "plane": "XY"})
    g = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "ProbeBed", "geometry": GEOMETRY, "constraints": PINS})
    log.note(f"probe bed: {g.get('status')} {json.dumps(g.get('detail'))[:200]}")
    accepted = []
    for spec in PROBES:
        r = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "ProbeBed", "constraints": [spec]})
        ok = r.get("status") not in ("INVALID_INPUT",) and not r.get("_isError")
        accepted.append(ok)
        log.note(f"{spec['type']}: status={r.get('status')} ids={sc(r).get('constraint_ids')} detail={json.dumps(r.get('detail'))[:160]}")
    log.check("each of the 16 types is accepted by sketch_add_constraint (probe)", all(accepted),
              f"{sum(accepted)}/16 accepted")
    info = await m.call("query_sketch_info", {"doc": doc, "sketch": "ProbeBed"})
    cons = sc(info).get("constraints") or []
    log.note(f"probe read-back ids={[c.get('id') for c in cons]} values={[(c.get('type'), c.get('value')) for c in cons if c.get('value')]}")
    await m.call("document_close", {"doc": doc})


go("tc-03-06-probe", body)
