"""Live check of query_mass_properties `objects` against the container FreeCAD (Story 13-6)."""

import ast
import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:18765/mcp"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
log: dict = {}

BUILD_SMALL = r"""
import json
doc.openTransaction("13-6 fixture")
import PartDesign  # noqa
for i, (name, size) in enumerate([("BodyA", (10, 20, 30)), ("BodyB", (5, 5, 5)), ("BodyC", (40, 8, 3))]):
    body = doc.addObject("PartDesign::Body", name)
    box = doc.addObject("PartDesign::AdditiveBox", name + "Box")
    body.addObject(box)
    box.Length, box.Width, box.Height = size
    body.Placement.Base = App.Vector(i * 60, 0, 0)
shell = doc.addObject("Part::Feature", "Shell")
shell.Shape = Part.makeBox(3, 4, 5).Shells[0]
shell.Placement.Base = App.Vector(0, 60, 0)
doc.addObject("App::DocumentObjectGroup", "Group")
doc.commitTransaction()
doc.recompute()
result = json.dumps(sorted(o.Name for o in doc.Objects))
"""

READ_DIRECT = r"""
import json
out = {}
for n in NAMES:
    o = doc.getObject(n)
    s = getattr(o, "Shape", None)
    if s is None or s.isNull():
        out[n] = None
        continue
    b = s.BoundBox
    out[n] = {"bbox": [b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax],
              "volume": s.Volume, "area": s.Area, "is_valid": bool(s.isValid()),
              "faces": len(s.Faces), "solids": len(s.Solids)}
result = json.dumps(out)
"""

BUILD_HEAVY = r"""
import json
doc.openTransaction("13-6 heavy")
base = Part.makeBox(200, 200, 20)
holes = [Part.makeCylinder(5, 20, App.Vector(20 + 20 * i, 20 + 20 * j, 0)) for i in range(9) for j in range(9)]
cut = base.cut(Part.makeCompound(holes))
top_circles = [e for e in cut.Edges if hasattr(e.Curve, "Radius") and abs(e.Vertexes[0].Point.z - 20) < 1e-6]
heavy = cut.makeFillet(1.0, top_circles)
heavy = heavy.makeFillet(2.0, [e for e in heavy.Edges if e.Curve.TypeId == "Part::GeomLine"
                               and abs(e.Vertexes[0].Point.z - 20) < 1e-6
                               and abs(e.Vertexes[1].Point.z - 20) < 1e-6])
names = []
for k in range(50):
    f = doc.addObject("Part::Feature", "Heavy%02d" % k)
    f.Shape = heavy.copy()
    f.Placement.Base = App.Vector((k % 10) * 220, 200 + (k // 10) * 220, 0)
    names.append(f.Name)
doc.commitTransaction()
doc.recompute()
result = json.dumps({"names": names, "faces": len(heavy.Faces), "edges": len(heavy.Edges),
                     "valid": bool(heavy.isValid()), "volume": heavy.Volume})
"""


def structured(res):
    sc = res.structuredContent
    if sc is None:
        raise RuntimeError(f"no structured content: {res.content}")
    if sc.get("status") != "OK" and not getattr(res, "_allow_error", False):
        pass
    return sc


async def call(session, tool, args):
    t0 = time.perf_counter()
    res = await session.call_tool(tool, args)
    dt = time.perf_counter() - t0
    return structured(res), dt, res


def exec_value(sc):
    payload = sc["structured_content"]
    if "value_repr" not in payload:
        raise RuntimeError(json.dumps(sc)[:3000])
    return json.loads(ast.literal_eval(payload["value_repr"]))


def unwrap(sc):
    """Return the tool's result object from the envelope."""
    for key in ("result", "structured_content"):
        if key in sc and isinstance(sc[key], dict):
            return sc[key]
    return sc


async def main():
    async with streamable_http_client(URL) as (read, write, *_):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name: t for t in (await session.list_tools()).tools}
            log["mass_schema"] = tools["query_mass_properties"].inputSchema
            listed, _, _ = await call(session, "document_list", {})
            for d in listed["structured_content"]["documents"]:
                await call(session, "document_close", {"doc": d["doc"]})
            created, _, _ = await call(session, "document_create", {"label": "verify_13_6"})
            log["document_create"] = created
            handle = created["structured_content"]["doc"]
            sc, _, _ = await call(session, "script_exec", {"doc": handle, "code": BUILD_SMALL})
            log["build_small"] = sc
            names = ["BodyA", "Shell", "BodyB", "Group", "BodyC", "BodyA"]
            multi, dt, raw = await call(
                session, "query_mass_properties", {"doc": handle, "objects": names}
            )
            log["objects_call"] = {"structured": multi, "elapsed_s": dt,
                                   "text": [c.text for c in raw.content if hasattr(c, "text")]}
            singles = {}
            for n in sorted(set(names)):
                sc, _, _ = await call(session, "query_mass_properties", {"doc": handle, "object": n})
                singles[n] = sc
            log["object_calls"] = singles
            direct_code = f"NAMES = {sorted(set(names))!r}\n" + READ_DIRECT
            sc, _, _ = await call(session, "script_exec", {"doc": handle, "code": direct_code})
            log["direct_read"] = exec_value(sc)
            bad = {}
            for label, args in {
                "both": {"doc": handle, "object": "BodyA", "objects": ["BodyA"]},
                "neither": {"doc": handle},
                "unknown": {"doc": handle, "objects": ["BodyA", "Nope"]},
                "fifty_one": {"doc": handle, "objects": ["BodyA"] * 51},
            }.items():
                res = await session.call_tool("query_mass_properties", args)
                bad[label] = {"isError": res.isError, "structured": res.structuredContent,
                              "text": [c.text for c in res.content if hasattr(c, "text")]}
            log["bad_inputs"] = bad
            sc, dt_build, _ = await call(session, "script_exec", {"doc": handle, "code": BUILD_HEAVY})
            heavy = exec_value(sc)
            heavy["build_s"] = dt_build
            log["heavy_build"] = heavy
            timings = []
            for _ in range(3):
                sc, dt, _ = await call(
                    session, "query_mass_properties", {"doc": handle, "objects": heavy["names"]}
                )
                timings.append(dt)
            log["heavy_call"] = {"elapsed_s": timings, "status": sc.get("status"),
                                 "record_count": len(unwrap(sc).get("objects", [])),
                                 "first_record": unwrap(sc).get("objects", [None])[0]}
            log["handle"] = handle
    (OUT / "live-13-6.json").write_text(json.dumps(log, indent=2, default=str))
    print("written", OUT / "live-13-6.json")


asyncio.run(main())
