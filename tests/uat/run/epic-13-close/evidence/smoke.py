"""Epic 13 close smoke: one fresh document, one short scenario per new tool family.

Usage (host, integration worktree):
    uv run python tests/uat/run/epic-13-close/evidence/smoke.py <out.json>
Talks to the container MCP proxy at http://127.0.0.1:18765/mcp. Leaves the document open for the
screenshot.
"""

import ast
import asyncio
import json
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:18765/mcp"


def q(value):
    return {"value": value, "unit": "mm"}


RECT = {
    "geometry": [
        {"kind": "line_segment", "start": [0, 0], "end": [20, 0]},
        {"kind": "line_segment", "start": [20, 0], "end": [20, 10]},
        {"kind": "line_segment", "start": [20, 10], "end": [0, 10]},
        {"kind": "line_segment", "start": [0, 10], "end": [0, 0]},
    ],
    "constraints": [
        {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
        {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
        {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1},
        {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
        {"type": "Horizontal", "first": 0},
        {"type": "Horizontal", "first": 2},
        {"type": "Vertical", "first": 1},
        {"type": "Vertical", "first": 3},
        {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2,
         "value": q(20), "name": "Width"},
        {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2,
         "value": q(10), "name": "Depth"},
    ],
}

SKETCH_HELPERS = """import Sketcher
P = App.Placement
V = App.Vector
R = App.Rotation

def rect(body, name, x0, y0, w, h, placement):
    s = doc.addObject('Sketcher::SketchObject', name)
    body.addObject(s)
    s.Placement = placement
    c = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    for i in range(4):
        s.addGeometry(Part.LineSegment(V(*c[i], 0), V(*c[(i + 1) % 4], 0)), False)
    for i in range(4):
        s.addConstraint(Sketcher.Constraint('Coincident', i, 2, (i + 1) % 4, 1))
    s.addConstraint(Sketcher.Constraint('Horizontal', 0)); s.addConstraint(Sketcher.Constraint('Horizontal', 2))
    s.addConstraint(Sketcher.Constraint('Vertical', 1)); s.addConstraint(Sketcher.Constraint('Vertical', 3))
    s.addConstraint(Sketcher.Constraint('DistanceX', -1, 1, 0, 1, x0))
    s.addConstraint(Sketcher.Constraint('DistanceY', -1, 1, 0, 1, y0))
    s.addConstraint(Sketcher.Constraint('DistanceX', 0, 1, 0, 2, w))
    s.addConstraint(Sketcher.Constraint('DistanceY', 1, 1, 1, 2, h))
    return s

def circle(body, name, cx, cy, r, placement):
    s = doc.addObject('Sketcher::SketchObject', name)
    body.addObject(s)
    s.Placement = placement
    s.addGeometry(Part.Circle(V(cx, cy, 0), V(0, 0, 1), r), False)
    s.addConstraint(Sketcher.Constraint('Radius', 0, r))
    s.addConstraint(Sketcher.Constraint('DistanceX', -1, 1, 0, 3, cx))
    s.addConstraint(Sketcher.Constraint('DistanceY', -1, 1, 0, 3, cy))
    return s
"""

LOFT_FIXTURE = SKETCH_HELPERS + """
body = doc.getObject('LoftBody')
body.Placement = P(V(80, 0, 0), R())
rect(body, 'LoftBase', -15, -15, 30, 30, P(V(0, 0, 0), R()))
circle(body, 'LoftMid', 0, 0, 12, P(V(0, 0, 20), R()))
rect(body, 'LoftTop', -8, -8, 16, 16, P(V(0, 0, 40), R()))
doc.recompute()
result = {o.Name: o.FullyConstrained for o in body.Group if o.TypeId.startswith('Sketcher')}
"""

SWEEP_FIXTURE = SKETCH_HELPERS + """
body = doc.getObject('SweepBody')
body.Placement = P(V(140, 0, 0), R())
circle(body, 'Ring', 0, 0, 3, P(V(0, 0, 0), R()))
s = doc.addObject('Sketcher::SketchObject', 'Path')
body.addObject(s)
s.Placement = P(V(0, 0, 0), R(V(1, 0, 0), 90))
s.addGeometry(Part.LineSegment(V(0, 0, 0), V(0, 30, 0)), False)
s.addConstraint(Sketcher.Constraint('Coincident', 0, 1, -1, 1))
s.addConstraint(Sketcher.Constraint('Vertical', 0))
s.addConstraint(Sketcher.Constraint('DistanceY', 0, 1, 0, 2, 30.0))
s.addGeometry(Part.ArcOfCircle(Part.Circle(V(-20, 30, 0), V(0, 0, 1), 20.0), 0.0, 1.5), False)
s.addConstraint(Sketcher.Constraint('Tangent', 0, 2, 1, 1))
s.addConstraint(Sketcher.Constraint('Radius', 1, 20.0))
s.addConstraint(Sketcher.Constraint('Angle', 1, 1.5))
doc.recompute()
result = {o.Name: o.FullyConstrained for o in body.Group if o.TypeId.startswith('Sketcher')}
"""

FACE_AT = (
    "faces = doc.getObject('Block').Shape.Faces\n"
    "def at(axis, value):\n"
    "    return [f'Face{i}' for i, f in enumerate(faces, 1)\n"
    "            if abs(getattr(f.BoundBox, axis + 'Min') - value) < 1e-6\n"
    "            and abs(getattr(f.BoundBox, axis + 'Max') - value) < 1e-6]\n"
)

FINGERPRINT = (
    "from freecad_buddy.usecases.fingerprint import fingerprint\n"
    "result = fingerprint(doc, fresh=True)['digest']"
)
BODY_PLACEMENT = (
    "result = [tuple(doc.Body.Placement.Base), "
    "round(doc.Body.Placement.Rotation.Angle * 57.29577951308232, 6)]"
)


class Run:
    def __init__(self, session):
        self.s = session
        self.out = []
        self.doc = None

    async def call(self, step, tool, args):
        if self.doc is not None:
            args = {"doc": self.doc, **args}
        t0 = time.time()
        res = await self.s.call_tool(tool, args)
        sc = res.structuredContent
        rec = {"step": step, "tool": tool, "args": args, "seconds": round(time.time() - t0, 3),
               "isError": res.isError, "structuredContent": sc,
               "text": [b.text for b in res.content if getattr(b, "type", "") == "text"]}
        self.out.append(rec)
        print(f"[{step}] {tool} -> {summary(rec)}", flush=True)
        return sc or {}

    async def py(self, step, code):
        sc = await self.call(step, "script_exec", {"code": code})
        text = (sc.get("structured_content") or {}).get("value_repr")
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError, TypeError):
            return text


def summary(rec):
    sc = rec["structuredContent"] or {}
    inner = sc.get("structured_content") or {}
    mutation = inner.get("mutation") or {}
    tnp = (mutation.get("post_verify") or {}).get("tnp_audit") or {}
    parts = [str(sc.get("status")), f"isError={rec['isError']}"]
    if mutation:
        parts.append(f"rolled_back={mutation.get('rolled_back')} tnp={tnp.get('status')}")
    vol = ((inner.get("feature_state") or {}).get("shape_summary") or {}).get("volume")
    if vol is not None:
        parts.append(f"volume={vol}")
    if "value_repr" in inner:
        parts.append(f"value={inner['value_repr']}"[:400])
    if rec["tool"] in ("query_interference", "document_undo", "query_placement",
                       "feature_set_parameters", "verify_recompute"):
        parts.append(" | ".join(rec["text"])[:900])
    if sc.get("status") not in ("OK", None):
        parts.append(str(sc.get("detail") or rec["text"])[:400])
    return " ".join(parts)


async def scenario(r):
    await r.call("setup", "document_list", {})
    sc = await r.call("setup", "document_create", {"label": "epic13_close"})
    r.doc = (sc.get("structured_content") or {}).get("doc") or sc.get("doc")

    # TC-21: Part primitives and booleans.
    box = {"length": q(10), "width": q(10), "height": q(10)}
    await r.call("TC-21", "feature_part_primitive", {"kind": "box", "name": "A", **box})
    await r.call("TC-21", "feature_part_primitive",
                 {"kind": "box", "name": "B", **box, "placement": {"base": {"x": q(5)}}})
    await r.call("TC-21", "feature_part_boolean",
                 {"operation": "cut", "base": "A", "tools": ["B"], "name": "CutAB"})
    await r.call("TC-21", "feature_part_boolean",
                 {"operation": "fuse", "base": "A", "tools": ["B"], "name": "FuseAB"})
    await r.py("TC-21", "result = [round(doc.CutAB.Shape.Volume, 6), round(doc.FuseAB.Shape.Volume, 6), "
               "doc.CutAB.TypeId, doc.FuseAB.TypeId, doc.A.Visibility, doc.B.Visibility]")

    # TC-17: touching versus overlapping solids.
    await r.call("TC-17", "feature_part_primitive",
                 {"kind": "box", "name": "C", **box, "placement": {"base": {"y": q(30)}}})
    await r.call("TC-17", "feature_part_primitive",
                 {"kind": "box", "name": "D", **box, "placement": {"base": {"x": q(10), "y": q(30)}}})
    await r.call("TC-17", "feature_part_primitive",
                 {"kind": "box", "name": "E", **box, "placement": {"base": {"y": q(30), "z": q(8)}}})
    before = await r.py("TC-17", FINGERPRINT)
    await r.call("TC-17", "query_interference", {"pairs": [["C", "D"], ["C", "E"]]})
    after = await r.py("TC-17", FINGERPRINT)
    print(f"[TC-17] fingerprint unchanged: {before == after}", flush=True)

    # TC-18: datum on the pad's top face follows a Length edit.
    await r.call("TC-18", "feature_body_create", {"name": "Body"})
    await r.call("TC-18", "sketch_create", {"name": "Profile", "plane": "XY", "body": "Body"})
    await r.call("TC-18", "sketch_add_geometry", {"sketch": "Profile", **RECT})
    await r.call("TC-18", "feature_pad",
                 {"body": "Body", "profile": "Profile", "name": "Block", "length": q(10)})
    top = await r.py("TC-18", FACE_AT + "result = at('Z', 10.0)")
    await r.call("TC-18", "feature_datum", {
        "body": "Body", "name": "TopDatum", "kind": "plane", "map_mode": "FlatFace",
        "attachment": {"kind": "mapped_name", "object": "Block", "mapped_name": top[0]}})
    await r.call("TC-18", "feature_set_parameters",
                 {"feature": "Block", "parameters": {"Length": q(15)}})
    await r.py("TC-18", "d = doc.getObject('TopDatum')\nresult = (round(d.Placement.Base.z, 6), "
               "d.AttachmentSupport[0][1], [o.Name for o in doc.Objects if not o.isValid()])")

    # TC-20: one-component placement write keeps the rest; a Label write reports the unique label.
    await r.py("TC-20", "doc.Body.Placement = App.Placement(App.Vector(-40, 2, 3), "
               "App.Rotation(App.Vector(0, 0, 1), 90))\ndoc.recompute()\n" + BODY_PLACEMENT)
    await r.call("TC-20", "feature_set_parameters",
                 {"feature": "Body", "parameters": {"Placement": {"base": {"x": q(-50)}}}})
    await r.call("TC-20", "query_placement", {"object": "Body"})
    await r.py("TC-20", BODY_PLACEMENT)
    await r.call("TC-20", "feature_set_parameters",
                 {"feature": "Block", "parameters": {"Label": "Profile"}})
    await r.py("TC-20", "result = doc.Block.Label")

    # 13-13: a script_exec write is one undo step.
    await r.py("13-13", "o = doc.addObject('Part::Feature', 'Scratch')\n"
               "o.Shape = Part.makeBox(2, 2, 2, App.Vector(0, -30, 0))\n"
               "doc.recompute()\nresult = doc.getObject('Scratch') is not None")
    await r.call("13-13", "document_undo", {})
    await r.py("13-13", "result = [doc.getObject('Scratch') is None, doc.Block.Label, len(doc.Objects)]")

    # 13-18: loft and sweep.
    await r.call("13-18", "feature_body_create", {"name": "LoftBody"})
    await r.py("13-18", LOFT_FIXTURE)
    await r.call("13-18", "feature_loft", {"body": "LoftBody", "profile": "LoftBase",
                                           "sections": ["LoftMid", "LoftTop"], "name": "Lofted"})
    await r.call("13-18", "feature_body_create", {"name": "SweepBody"})
    await r.py("13-18", SWEEP_FIXTURE)
    await r.call("13-18", "feature_sweep", {"body": "SweepBody", "profile": "Ring", "spine": "Path",
                                            "mode": "frenet", "name": "Swept"})
    await r.py("13-18", "l, s = doc.Lofted.Shape, doc.Swept.Shape\nresult = [l.isValid(), len(l.Solids), "
               "[round(v, 3) for v in (l.BoundBox.XMin, l.BoundBox.XMax, l.BoundBox.ZMin, l.BoundBox.ZMax)], "
               "s.isValid(), len(s.Solids), round(s.Volume, 3), round(3.141592653589793 * 9 * 60, 3)]")

    # Final state.
    await r.py("final", "doc.CutAB.Visibility = False\nresult = 'set'")
    await r.call("final", "verify_recompute", {})
    await r.call("final", "query_tree_summary", {})
    await r.call("final", "view_fit_viewport", {})


async def main(out_path):
    async with streamablehttp_client(URL, timeout=60, sse_read_timeout=300) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            run = Run(s)
            try:
                await scenario(run)
            finally:
                with open(out_path, "w", encoding="utf-8") as fh:
                    json.dump(run.out, fh, indent=1)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
