"""TC-12-12 Given: a plate whose recompute is slow - an N x N grid of pocketed holes, built over MCP.

Usage: python tc-12-12-build.py <N>   prints the doc handle and the pocket commit time.
"""
import asyncio
import json
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EV = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-03-04/evidence"
N = int(sys.argv[1])
PITCH = 4.0
SIZE = N * PITCH + PITCH


def mm(v):
    return {"value": v, "unit": "mm"}


def plate():
    c = [(0, 0), (SIZE, 0), (SIZE, SIZE), (0, SIZE)]
    geometry = [{"kind": "line_segment", "start": list(c[i]), "end": list(c[(i + 1) % 4])} for i in range(4)]
    constraints = [{"type": "Coincident", "first": i, "first_pos": 2, "second": (i + 1) % 4, "second_pos": 1} for i in range(4)]
    constraints += [
        {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
        {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
        {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": mm(SIZE)},
        {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": mm(SIZE)},
    ]
    return {"geometry": geometry, "constraints": constraints}


def holes():
    geometry, constraints = [], []
    for i in range(N):
        for j in range(N):
            k = len(geometry)
            x, y = PITCH + i * PITCH, PITCH + j * PITCH
            geometry.append({"kind": "circle", "center": [x, y], "radius": mm(1.0)})
            constraints += [
                {"type": "DistanceX", "first": -1, "first_pos": 1, "second": k, "second_pos": 3, "value": mm(x)},
                {"type": "DistanceY", "first": -1, "first_pos": 1, "second": k, "second_pos": 3, "value": mm(y)},
                {"type": "Diameter", "first": k, "value": mm(2.0)},
            ]
    return {"geometry": geometry, "constraints": constraints}


async def main():
    log = open(f"{EV}/tc-12-12-mcp.jsonl", "a", encoding="utf-8")
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()

            async def call(tool, args):
                t0 = time.time()
                res = await s.call_tool(tool, args)
                env = json.loads("".join(b.text for b in res.content if hasattr(b, "text")))
                el = round(time.time() - t0, 2)
                log.write(json.dumps({"tool": tool, "elapsed_s": el, "status": env.get("status"), "detail": env.get("detail")})[:2000] + "\n")
                return env, el

            async def mutate(doc, tool, args):
                p, _ = await call("preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": args}})
                pid = (p.get("structured_content") or {}).get("preview_id")
                if not pid:
                    raise SystemExit(f"preview failed {tool}: {json.dumps(p)[:600]}")
                env, el = await call(tool, {"doc": doc, **args, "confirm": {"preview_id": pid, "elicitation_action": "accept"}})
                if env.get("status") != "OK":
                    raise SystemExit(f"{tool} failed: {json.dumps(env)[:600]}")
                return el

            doc = (await call("document_create", {"label": "tc12-slow"}))[0]["structured_content"]["doc"]
            await mutate(doc, "feature_body_create", {"name": "Body"})
            await mutate(doc, "sketch_create", {"name": "Sketch", "plane": "XY", "body": "Body"})
            await mutate(doc, "sketch_add_geometry", {"sketch": "Sketch", **plate()})
            await mutate(doc, "feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad", "length": mm(6)})
            await mutate(doc, "sketch_create", {"name": "Holes", "plane": "XY", "body": "Body"})
            el_geo = await mutate(doc, "sketch_add_geometry", {"sketch": "Holes", **holes()})
            el = await mutate(doc, "feature_pocket", {"body": "Body", "profile": "Holes", "name": "Pocket", "length": mm(6), "reversed": True})
            print(json.dumps({"doc": doc, "holes": N * N, "geometry_commit_s": el_geo, "pocket_commit_s": el}))


asyncio.run(main())
