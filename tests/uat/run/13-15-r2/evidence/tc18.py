"""TC-18 driver: run one scenario against the container MCP proxy and save every call.

Usage (host, from the worktree): uv run python tests/uat/run/13-15-r1/evidence/tc18.py <id> <out.json>
<id> is 01, 02, 03a, 03b, 03c or 04. Each scenario opens its own document. With KEEP=1 the
document stays open (for the screenshot); otherwise the scenario closes it.
"""

import ast
import asyncio
import json
import os
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:18765/mcp"
MM = "mm"


def q(value):
    return {"value": value, "unit": MM}


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
CIRCLE = {
    "geometry": [{"kind": "circle", "center": [0, 0], "radius": q(5)}],
    "constraints": [
        {"type": "Coincident", "first": 0, "first_pos": 3, "second": -1, "second_pos": 1},
        {"type": "Radius", "first": 0, "value": q(5), "name": "Radius"},
    ],
}

FACE_AT = (
    "faces = doc.getObject('Block').Shape.Faces\n"
    "def at(axis, value):\n"
    "    return [f'Face{i}' for i, f in enumerate(faces, 1)\n"
    "            if abs(getattr(f.BoundBox, axis + 'Min') - value) < 1e-6\n"
    "            and abs(getattr(f.BoundBox, axis + 'Max') - value) < 1e-6]\n"
)


class Run:
    def __init__(self, session):
        self.s = session
        self.out = []
        self.doc = None

    async def call(self, tool, args):
        if self.doc is not None:
            args = {"doc": self.doc, **args}
        t0 = time.time()
        res = await self.s.call_tool(tool, args)
        sc = res.structuredContent
        rec = {"tool": tool, "args": args, "seconds": round(time.time() - t0, 3),
               "isError": res.isError, "structuredContent": sc,
               "text": [b.text for b in res.content if getattr(b, "type", "") == "text"]}
        self.out.append(rec)
        print(f"-- {tool} -> {summary(rec)}")
        return sc or {}

    async def py(self, code):
        sc = await self.call("script_exec", {"code": code})
        text = (sc.get("structured_content") or {}).get("value_repr")
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError, TypeError):
            return text

    async def build(self, label, profile):
        sc = await self.call("document_create", {"label": label})
        self.doc = (sc.get("structured_content") or {}).get("doc") or sc.get("doc")
        await self.call("feature_body_create", {"name": "Body"})
        await self.call("sketch_create", {"name": "Profile", "plane": "XY", "body": "Body"})
        await self.call("sketch_add_geometry", {"sketch": "Profile", **profile})
        await self.call("feature_pad", {"body": "Body", "profile": "Profile", "name": "Block",
                                        "length": q(10)})

    async def datum(self, name, face, kind="plane", map_mode="FlatFace", obj="Block"):
        return await self.call("feature_datum", {
            "body": "Body", "name": name, "kind": kind, "map_mode": map_mode,
            "attachment": {"kind": "mapped_name", "object": obj, "mapped_name": face}})


def summary(rec):
    sc = rec["structuredContent"] or {}
    inner = sc.get("structured_content") or {}
    mutation = inner.get("mutation") or {}
    pv = mutation.get("post_verify") or {}
    tnp = pv.get("tnp_audit") or {}
    parts = [str(sc.get("status")), f"isError={rec['isError']}"]
    if mutation:
        parts.append(f"rolled_back={mutation.get('rolled_back')}")
        parts.append(f"tnp={tnp.get('status')} counts={tnp.get('counts')}")
        for f in tnp.get("findings") or []:
            parts.append(f"finding={f.get('owner')}.{f.get('prop')} {f.get('verdict')} "
                         f"L{f.get('layer')} {str(f.get('detail'))[:160]}")
    if "value_repr" in inner:
        parts.append(f"value={inner['value_repr']}"[:400])
    if sc.get("status") not in ("OK", None) and not mutation:
        parts.append(str(sc.get("detail") or rec["text"])[:300])
    return " ".join(parts)


async def s01(r):
    await r.build("tc18_01_pad_length", RECT)
    top = await r.py(FACE_AT + "result = at('Z', 10.0)")
    await r.datum("TopDatum", top[0])
    await r.py("result = doc.getObject('TopDatum').Placement.Base.z")
    await r.call("feature_set_parameters", {"feature": "Block", "parameters": {"Length": q(15)}})
    await r.py("d = doc.getObject('TopDatum')\n"
               "result = (round(d.Placement.Base.z, 6), d.AttachmentSupport[0][1], "
               "[o.Name for o in doc.Objects if not o.isValid()])")
    await r.call("view_fit_viewport", {})


async def s02(r):
    await r.build("tc18_02_sketch_width", RECT)
    faces = await r.py(FACE_AT + "result = (at('Z', 10.0), at('X', 20.0))")
    await r.datum("TopDatum", faces[0][0])
    await r.datum("SideDatum", faces[1][0])
    await r.call("sketch_set_datum", {"sketch": "Profile", "constraint": "Width", "value": q(30)})
    await r.py("t, s = doc.getObject('TopDatum'), doc.getObject('SideDatum')\n"
               "result = (round(t.Placement.Base.z, 6), round(s.Placement.Base.x, 6), "
               "round(doc.getObject('Block').Shape.BoundBox.XMax, 6), "
               "[o.Name for o in doc.Objects if not o.isValid()])")


PLANT = (
    "from freecad_buddy.usecases import tnp_guard\n"
    "d = doc.getObject('TopDatum')\n"
    "snap = tnp_guard.snapshot_references(doc)\n"
    "{change}\n"
    "doc.recompute()\n"
    "audit = tnp_guard.audit_references(doc, snap)\n"
    "result = (audit['status'], [(f['owner'], f['prop'], f['verdict'], f['layer'], "
    "str(f.get('detail'))[:120]) for f in audit['findings'] if f['owner'] == 'TopDatum'])\n"
)


async def s03a(r):
    await r.build("tc18_03a_planted_repoint", RECT)
    faces = await r.py(FACE_AT + "result = (at('Z', 10.0), at('Z', 0.0))")
    await r.datum("TopDatum", faces[0][0])
    # A re-point the op did not write: the datum now names the bottom face.
    await r.py(PLANT.format(change=f"d.AttachmentSupport = [(doc.getObject('Block'), ('{faces[1][0]}',))]"))
    await r.py("import inspect\nfrom freecad_buddy.usecases import tnp_guard\n"
               "result = tnp_guard.__file__")


async def s03a2(r):
    await r.build("tc18_03a2_planted_witness", RECT)
    top = await r.py(FACE_AT + "result = at('Z', 10.0)")
    await r.datum("TopDatum", top[0])
    # Witness tamper with the support unchanged: the snapshot says the face was 5 mm lower.
    change = ("rec = next(x for x in snap if x['owner'] == 'TopDatum')\n"
              "w = rec['entries'][0]['witness']\n"
              "rec['entries'][0]['witness'] = (w[0], w[1], w[2], w[3] - 5, w[4], w[5], w[6] - 5)")
    await r.py(PLANT.format(change=change))


async def s03b(r):
    await r.build("tc18_03b_reversed", RECT)
    top = await r.py(FACE_AT + "result = at('Z', 10.0)")
    await r.datum("TopDatum", top[0])
    await r.call("feature_set_parameters", {"feature": "Block", "parameters": {"Reversed": True}})
    await r.py("b = doc.getObject('Block')\n"
               "result = (b.Reversed, round(doc.getObject('TopDatum').Placement.Base.z, 6), "
               "round(b.Shape.BoundBox.ZMin, 6), round(b.Shape.BoundBox.ZMax, 6))")


async def s03c(r):
    await r.build("tc18_03c_vertical_edge", RECT)
    edge = await r.py(
        "es = doc.getObject('Block').Shape.Edges\n"
        "result = [f'Edge{i}' for i, e in enumerate(es, 1) if abs(e.BoundBox.XMin - 20) < 1e-6 "
        "and abs(e.BoundBox.XMax - 20) < 1e-6 and abs(e.BoundBox.YMin) < 1e-6 "
        "and abs(e.BoundBox.YMax) < 1e-6]")
    edge = edge[0]
    await r.datum("EdgeAxis", edge, kind="axis", map_mode="TwoPointLine")
    await r.py("a = doc.getObject('EdgeAxis')\nresult = (a.MapMode, a.isValid(), a.AttachmentSupport[0][1])")
    await r.call("feature_set_parameters", {"feature": "Block", "parameters": {"Length": q(15)}})
    await r.py("a = doc.getObject('EdgeAxis')\nb = doc.getObject('Block')\n"
               "result = (round(b.Length.Value, 6), a.isValid())")


async def s04(r):
    await r.build("tc18_04_curved_face", CIRCLE)
    side = await r.py(
        "fs = doc.getObject('Block').Shape.Faces\n"
        "result = [f'Face{i}' for i, f in enumerate(fs, 1) if f.Surface.TypeId == 'Part::GeomCylinder']")
    side = side[0]
    await r.datum("CurvedPoint", side, kind="point", map_mode="CenterOfMass")
    await r.call("view_fit_viewport", {})
    probe = (
        "import Part\n"
        f"f = doc.getObject('Block').Shape.getElement('{side}')\n"
        "bb, ob = f.BoundBox, f.optimalBoundingBox()\n"
        "tri = f.getTriangulation() if hasattr(f, 'getTriangulation') else None\n"
        "p = doc.getObject('CurvedPoint')\n"
        "result = dict(bbox=[round(v, 9) for v in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)], "
        "optimal=[round(v, 9) for v in (ob.XMin, ob.YMin, ob.ZMin, ob.XMax, ob.YMax, ob.ZMax)], "
        "triangles=(len(tri[1]) if tri and tri[1] else 0), point_z=round(p.Placement.Base.z, 6), "
        "valid=p.isValid())"
    )
    await r.py(probe)
    await r.call("feature_set_parameters", {"feature": "Block", "parameters": {"Length": q(15)}})
    await r.py(probe)


async def s04b(r):
    """R1-D1 variant: the curved face is not on the support's bounding box (a boss on a block)."""
    await r.build("tc18_04b_inner_curved_face", RECT)
    await r.call("sketch_create", {"name": "BossProfile", "plane": "XY", "body": "Body"})
    await r.call("sketch_add_geometry", {"sketch": "BossProfile", "geometry": [
        {"kind": "circle", "center": [10, 5], "radius": q(3)}], "constraints": [
        {"type": "DistanceX", "first": -1, "first_pos": 1, "second": 0, "second_pos": 3, "value": q(10)},
        {"type": "DistanceY", "first": -1, "first_pos": 1, "second": 0, "second_pos": 3, "value": q(5)},
        {"type": "Radius", "first": 0, "value": q(3)}]})
    await r.call("feature_pad", {"body": "Body", "profile": "BossProfile", "name": "Boss", "length": q(15)})
    side = await r.py(
        "fs = doc.getObject('Boss').Shape.Faces\n"
        "result = [f'Face{i}' for i, f in enumerate(fs, 1) if f.Surface.TypeId == 'Part::GeomCylinder']")
    await r.datum("BossPoint", side[0], kind="point", map_mode="CenterOfMass", obj="Boss")
    await r.call("view_fit_viewport", {})
    probe = (
        f"f = doc.getObject('Boss').Shape.getElement('{side[0]}')\n"
        "b, s = f.BoundBox, doc.getObject('Boss').Shape.BoundBox\n"
        "p = doc.getObject('BossPoint')\n"
        "result = dict(face=[round(v, 9) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)], "
        "support=[round(v, 9) for v in (s.XMin, s.YMin, s.ZMin, s.XMax, s.YMax, s.ZMax)], "
        "point_z=round(p.Placement.Base.z, 6), valid=p.isValid())"
    )
    await r.py(probe)
    await r.call("feature_set_parameters", {"feature": "Boss", "parameters": {"Length": q(20)}})
    await r.py(probe)


SCENARIOS = {"01": s01, "02": s02, "03a": s03a, "03a2": s03a2, "03b": s03b, "03c": s03c,
             "04": s04, "04b": s04b}


async def main(scenario, out_path):
    async with streamablehttp_client(URL, timeout=60, sse_read_timeout=300) as (rd, wr, _):
        async with ClientSession(rd, wr) as session:
            await session.initialize()
            r = Run(session)
            try:
                await SCENARIOS[scenario](r)
            finally:
                if r.doc and os.environ.get("KEEP") != "1":
                    await r.call("document_close", {})
                json.dump(r.out, open(out_path, "w", encoding="utf-8"), indent=1)


asyncio.run(main(sys.argv[1], sys.argv[2]))
