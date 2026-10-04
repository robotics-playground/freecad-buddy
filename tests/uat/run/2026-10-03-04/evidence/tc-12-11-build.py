"""TC-12-11 Given: one document with 5 Bodies (Sketch + Pad each) = 55 objects, built over MCP."""
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EV = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-03-04/evidence"


def rectangle(width, height, x0):
    corners = [(x0, 0), (x0 + width, 0), (x0 + width, height), (x0, height)]
    geometry = [{"kind": "line_segment", "start": list(corners[i]), "end": list(corners[(i + 1) % 4])} for i in range(4)]
    constraints = [{"type": "Coincident", "first": i, "first_pos": 2, "second": (i + 1) % 4, "second_pos": 1} for i in range(4)]
    constraints += [
        {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
        {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
        {"type": "DistanceX", "first": -1, "first_pos": 1, "second": 0, "second_pos": 1, "value": {"value": x0, "unit": "mm"}},
        {"type": "DistanceY", "first": -1, "first_pos": 1, "second": 0, "second_pos": 1, "value": {"value": 0, "unit": "mm"}},
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": width, "unit": "mm"}},
        {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": {"value": height, "unit": "mm"}},
    ]
    return {"geometry": geometry, "constraints": constraints}


async def main():
    log = open(f"{EV}/tc-12-11-mcp.jsonl", "a", encoding="utf-8")
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()

            async def call(tool, args):
                res = await s.call_tool(tool, args)
                env = json.loads("".join(b.text for b in res.content if hasattr(b, "text")))
                log.write(json.dumps({"tool": tool, "args": args, "envelope": env})[:4000] + "\n")
                return env

            async def mutate(doc, tool, args):
                p = await call("preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": args}})
                pid = (p.get("structured_content") or {}).get("preview_id")
                if not pid:
                    raise SystemExit(f"preview failed {tool}: {json.dumps(p)[:600]}")
                env = await call(tool, {"doc": doc, **args, "confirm": {"preview_id": pid, "elicitation_action": "accept"}})
                if env.get("status") != "OK":
                    raise SystemExit(f"{tool} failed: {json.dumps(env)[:600]}")

            doc = (await call("document_create", {"label": "tc12-large"}))["structured_content"]["doc"]
            for i in range(5):
                suffix = "" if i == 0 else f"{i:03d}"
                body, sketch, pad = f"Body{suffix}", f"Sketch{suffix}", f"Pad{suffix}"
                await mutate(doc, "feature_body_create", {"name": body})
                await mutate(doc, "sketch_create", {"name": sketch, "plane": "XY", "body": body})
                await mutate(doc, "sketch_add_geometry", {"sketch": sketch, **rectangle(10, 10, i * 15)})
                await mutate(doc, "feature_pad", {"body": body, "profile": sketch, "name": pad, "length": {"value": 5, "unit": "mm"}})
            print(doc)


asyncio.run(main())
