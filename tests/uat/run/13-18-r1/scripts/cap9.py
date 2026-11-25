"""CAP-9 live check for Story 13-18 over MCP (http://127.0.0.1:18765/mcp).

`cap9.py build <state.json> <transcript.json>`: three documents, fixture sketches by script_exec
(one transaction each), then the typed tools under test: feature_loft (3 sections, additive),
feature_sweep (sketch spine line + arc, additive, frenet), feature_sweep subtractive (groove in a
padded plate). `cap9.py undo <state.json> <transcript.json>`: one document_undo per document with
expect_fingerprint = that call's fingerprint_before.
"""

import asyncio
import json
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:18765/mcp"
PHASE, STATE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
log = []

RECT = """
def rect(name, x0, y0, w, h, placement):
    s = doc.addObject('Sketcher::SketchObject', name)
    body.addObject(s)
    s.Placement = placement
    c = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    for i in range(4):
        s.addGeometry(Part.LineSegment(App.Vector(*c[i], 0), App.Vector(*c[(i + 1) % 4], 0)), False)
    for i in range(4):
        s.addConstraint(Sketcher.Constraint('Coincident', i, 2, (i + 1) % 4, 1))
    s.addConstraint(Sketcher.Constraint('Horizontal', 0)); s.addConstraint(Sketcher.Constraint('Horizontal', 2))
    s.addConstraint(Sketcher.Constraint('Vertical', 1)); s.addConstraint(Sketcher.Constraint('Vertical', 3))
    s.addConstraint(Sketcher.Constraint('DistanceX', -1, 1, 0, 1, x0))
    s.addConstraint(Sketcher.Constraint('DistanceY', -1, 1, 0, 1, y0))
    s.addConstraint(Sketcher.Constraint('DistanceX', 0, 1, 0, 2, w))
    s.addConstraint(Sketcher.Constraint('DistanceY', 1, 1, 1, 2, h))
    return s

def circle(name, cx, cy, r, placement):
    s = doc.addObject('Sketcher::SketchObject', name)
    body.addObject(s)
    s.Placement = placement
    s.addGeometry(Part.Circle(App.Vector(cx, cy, 0), App.Vector(0, 0, 1), r), False)
    s.addConstraint(Sketcher.Constraint('Radius', 0, r))
    s.addConstraint(Sketcher.Constraint('DistanceX', -1, 1, 0, 3, cx))
    s.addConstraint(Sketcher.Constraint('DistanceY', -1, 1, 0, 3, cy))
    return s
"""

HEAD = "import Sketcher\nP = App.Placement\nV = App.Vector\nR = App.Rotation\ndoc.openTransaction('fixture')\nbody = doc.getObject('Body')\n"
TAIL = "\ndoc.recompute()\ndoc.commitTransaction()\nresult = {o.Name: (o.TypeId, getattr(o, 'FullyConstrained', None)) for o in doc.Objects if o.TypeId.startswith('Sketcher')}\n"

LOFT_FIXTURE = HEAD + RECT + """
rect('Base', -15, -15, 30, 30, P(V(0, 0, 0), R()))
circle('Mid', 0, 0, 12, P(V(0, 0, 20), R()))
rect('Top', -8, -8, 16, 16, P(V(0, 0, 40), R()))
""" + TAIL

SWEEP_FIXTURE = HEAD + RECT + """
circle('Ring', 0, 0, 3, P(V(0, 0, 0), R()))
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
""" + TAIL

GROOVE_FIXTURE = HEAD + RECT + """
rect('PlateSketch', 0, 0, 60, 40, P(V(0, 0, 0), R()))
circle('Ring', 20, 10, 4, P(V(-5, 0, 0), R(V(1, 1, 1), 120)))
s = doc.addObject('Sketcher::SketchObject', 'Path')
body.addObject(s)
s.Placement = P(V(0, 0, 10), R())
s.addGeometry(Part.LineSegment(V(-5, 20, 0), V(65, 20, 0)), False)
s.addConstraint(Sketcher.Constraint('DistanceX', -1, 1, 0, 1, -5.0))
s.addConstraint(Sketcher.Constraint('DistanceY', -1, 1, 0, 1, 20.0))
s.addConstraint(Sketcher.Constraint('Horizontal', 0))
s.addConstraint(Sketcher.Constraint('DistanceX', 0, 1, 0, 2, 70.0))
""" + TAIL


def dump():
    with open(OUT, "w") as out:
        json.dump(log, out, indent=1, default=str)


async def call(s, step, tool, args):
    t = time.perf_counter()
    r = await s.call_tool(tool, args)
    sc = r.structuredContent or {}
    entry = {"step": step, "tool": tool, "args": args, "isError": r.isError,
             "elapsed_s": round(time.perf_counter() - t, 3), "result": sc}
    if not sc:
        entry["text"] = [c.text for c in r.content if getattr(c, "text", None)][:1]
    log.append(entry)
    dump()
    d = sc.get("detail") or {}
    body = sc.get("structured_content") or {}
    m = body.get("mutation") or {}
    print(f"[{step}] {tool} status={sc.get('status')} code={d.get('code')} "
          f"elapsed={entry['elapsed_s']} undo_steps={body.get('undo_steps')} "
          f"rolled_back={m.get('rolled_back')} msg={(d.get('message') or '')[:200]} "
          f"text={entry.get('text')}", flush=True)
    return sc


def mm(v):
    return {"value": v, "unit": "mm"}


async def build(s):
    state = {}
    plan = [("LoftPart", LOFT_FIXTURE), ("SweepPart", SWEEP_FIXTURE), ("GroovePart", GROOVE_FIXTURE)]
    for label, fixture in plan:
        created = await call(s, f"{label}.create", "document_create", {"label": label})
        handle = created["structured_content"]["doc"]
        state[label] = {"doc": handle}
        await call(s, f"{label}.body", "feature_body_create", {"doc": handle, "name": "Body"})
        await call(s, f"{label}.fixture", "script_exec", {"doc": handle, "code": fixture})
    groove = state["GroovePart"]["doc"]
    await call(s, "GroovePart.pad", "feature_pad",
               {"doc": groove, "body": "Body", "profile": "PlateSketch", "name": "Plate",
                "length": mm(10)})
    runs = [
        ("LoftPart", "feature_loft", {"doc": state["LoftPart"]["doc"], "body": "Body",
                                      "profile": "Base", "sections": ["Mid", "Top"],
                                      "name": "Lofted"}),
        ("SweepPart", "feature_sweep", {"doc": state["SweepPart"]["doc"], "body": "Body",
                                        "profile": "Ring", "spine": "Path", "mode": "frenet",
                                        "name": "Swept"}),
        ("GroovePart", "feature_sweep", {"doc": groove, "body": "Body", "profile": "Ring",
                                         "spine": "Path", "subtractive": True,
                                         "name": "Groove"}),
    ]
    for label, tool, args in runs:
        env = await call(s, f"{label}.op", tool, args)
        mutation = (env.get("structured_content") or {}).get("mutation") or {}
        state[label]["fingerprint_before"] = mutation.get("fingerprint_before")
        state[label]["feature"] = args["name"]
        await call(s, f"{label}.query", "query_object",
                   {"doc": state[label]["doc"], "object": args["name"]})
    with open(STATE, "w") as out:
        json.dump(state, out, indent=1)


async def undo(s):
    state = json.load(open(STATE))
    for label, entry in state.items():
        await call(s, f"{label}.undo", "document_undo",
                   {"doc": entry["doc"], "expect_fingerprint": entry["fingerprint_before"]})
        await call(s, f"{label}.tree", "query_tree_summary", {"doc": entry["doc"]})


async def main():
    async with streamable_http_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            await (build(s) if PHASE == "build" else undo(s))


asyncio.run(main())
