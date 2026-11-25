"""Timing of query_section on the largest allowed inputs, in the container."""

import asyncio
import json
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:18765/mcp"
OUT = sys.argv[1]

BOXES = r"""
import Part, FreeCAD
side = int(math.ceil(math.sqrt(N)))
solids = [Part.makeBox(2, 2, 10, FreeCAD.Vector(4 * (i % side), 4 * (i // side), 0)) for i in range(N)]
obj = doc.addObject("Part::Feature", NAME)
obj.Shape = Part.makeCompound(solids)
result = [len(obj.Shape.Faces), len(obj.Shape.Solids), obj.Shape.isValid()]
"""

PLATE = r"""
import Part, FreeCAD
V = FreeCAD.Vector
side = int(math.ceil(math.sqrt(N)))
size = 4 * side + 4
outer = Part.Wire(Part.makePolygon([V(0,0,0), V(size,0,0), V(size,size,0), V(0,size,0), V(0,0,0)]))
holes = [Part.Wire(Part.makeCircle(1, V(4 + 4 * (i % side), 4 + 4 * (i // side), 0))) for i in range(N)]
obj = doc.addObject("Part::Feature", NAME)
obj.Shape = Part.makeFace([outer] + holes, "Part::FaceMakerCheese").extrude(V(0, 0, 5))
result = [len(obj.Shape.Faces), len(obj.Shape.Solids), obj.Shape.isValid()]
"""

CASES = [
    ("compound 1,666 boxes (9,996 faces, 1,666 wires) run 2", BOXES, 1666, "Boxes1666", 5),
    ("compound 1,500 boxes (9,000 faces, 1,500 wires, area measured) run 2", BOXES, 1500, "Boxes1500", 5),
    ("compound 1,667 boxes (10,002 faces, refused)", BOXES, 1667, "Boxes1667", 5),
]


async def call(session, name, args):
    start = time.perf_counter()
    reply = await session.call_tool(name, args)
    return (reply.structuredContent or {}), time.perf_counter() - start


async def main():
    log = []
    async with streamable_http_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            created, _ = await call(session, "document_create", {"label": "SectionTiming"})
            doc = created["structured_content"]["doc"]
            for label, builder, n, name, offset in CASES:
                code = f"import math\nN = {n}\nNAME = {name!r}\n" + builder
                built, build_s = await call(session, "script_exec", {"doc": doc, "code": code})
                body, secs = await call(session, "query_section", {
                    "doc": doc, "object": name,
                    "plane": {"normal": "z", "offset": {"value": offset, "unit": "mm"}}})
                after, after_s = await call(session, "document_list", {})
                sc = body.get("structured_content") or {}
                row = {"label": label, "built": (built.get("structured_content") or {}).get("value_repr"),
                       "build_status": built.get("status"), "build_s": round(build_s, 2),
                       "status": body.get("status"), "detail": (body.get("detail") or {}).get("code"),
                       "message": (body.get("detail") or {}).get("message"),
                       "wires": sc.get("wires"), "closed": sc.get("closed_wires"), "area": sc.get("area"),
                       "length": sc.get("length"), "elapsed_s": round(secs, 2),
                       "bridge_after": after.get("status"), "bridge_after_s": round(after_s, 2)}
                print(json.dumps(row), flush=True)
                log.append(row)
            await call(session, "document_close", {"doc": doc})
    with open(OUT, "w") as fh:
        json.dump(log, fh, indent=1)


asyncio.run(main())
