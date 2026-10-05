"""Story 10.4 UAT driver. Usage: run.py <phase> [args...]. Every call is appended to mcp-<phase>.jsonl."""
import asyncio, json, os, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVID = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-05-01/evidence"
PHASE = sys.argv[1]
LOG = open(f"{EVID}/mcp-{os.environ.get('LOGTAG', PHASE)}.jsonl", "a", encoding="utf-8")


def q(v, u="mm"):
    return {"value": v, "unit": u}


def rect(w, h):
    pts = [(0, 0), (w, 0), (w, h), (0, h)]
    g = [{"kind": "line_segment", "start": list(pts[i]), "end": list(pts[(i + 1) % 4])} for i in range(4)]
    c = [{"type": "Coincident", "first": i, "first_pos": 2, "second": (i + 1) % 4, "second_pos": 1} for i in range(4)]
    c += [{"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
          {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
          {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": q(w)},
          {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": q(h)},
          {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1}]
    return g, c


async def call(s, tool, args):
    r = await s.call_tool(tool, args)
    text = "".join(b.text for b in r.content if hasattr(b, "text"))
    try:
        env = json.loads(text)
    except json.JSONDecodeError:
        env = {"_raw": text}
    LOG.write(json.dumps({"tool": tool, "args": args, "envelope": env}) + "\n")
    LOG.flush()
    return env


async def apply(s, doc, tool, args):
    p = await call(s, "preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": args}})
    tok = (p.get("structured_content") or {}).get("preview_id")
    return await call(s, tool, dict(args, doc=doc, confirm={"preview_id": tok, "elicitation_action": "accept"}))


def brief(e):
    return json.dumps({"status": e.get("status"), "detail": e.get("detail"), "text": e.get("text")})[:1500]


def sc(e):
    return json.dumps(e.get("structured_content"))[:3000]


async def body_pad(s, doc, w=20, h=30, length=10):
    print("body", brief(await apply(s, doc, "feature_body_create", {"name": "Body"})))
    print("sketch", brief(await apply(s, doc, "sketch_create", {"name": "Sketch", "body": "Body", "plane": "XY"})))
    g, c = rect(w, h)
    print("geo", brief(await apply(s, doc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": g, "constraints": c})))
    print("pad", brief(await apply(s, doc, "feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(length)})))


async def main():
    args = sys.argv[2:]
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if PHASE == "call":
                # generic: call <tool> <json>
                e = await call(s, args[0], json.loads(args[1]))
                print(json.dumps(e, indent=1)[:6000])
            elif PHASE == "s1-setup":
                e = await call(s, "document_open", {"path": f"{EVID}/s1-box.FCStd"})
                doc = e["structured_content"]["doc"]
                print("doc", doc)
                await body_pad(s, doc)
                print("tree", sc(await call(s, "query_tree_summary", {"doc": doc, "depth": 3})))
            elif PHASE == "s2-setup":
                e = await call(s, "document_open", {"path": f"{EVID}/s2-box.FCStd"})
                doc = e["structured_content"]["doc"]
                print("doc", doc)
                await body_pad(s, doc)
                print("tree", sc(await call(s, "query_tree_summary", {"doc": doc, "depth": 3})))
            elif PHASE == "s4-setup":
                e = await call(s, "document_create", {"label": "S4DatumPad"})
                doc = e["structured_content"]["doc"]
                print("doc", doc)
                await body_pad(s, doc)
                print("datum", brief(await apply(s, doc, "feature_datum", {
                    "body": "Body", "name": "DatumPlane", "kind": "plane",
                    "attachment": {"kind": "mapped_name", "object": "XY_Plane"}, "map_mode": "FlatFace",
                    "offset": q(5)})))
                print("tree", sc(await call(s, "query_tree_summary", {"doc": doc, "depth": 3})))
            elif PHASE == "datum":
                doc = args[0]
                print("datum", brief(await apply(s, doc, "feature_datum", {
                    "body": "Body", "name": "DatumPlane", "kind": "plane",
                    "attachment": {"kind": "mapped_name", "object": "XY_Plane"}, "map_mode": "FlatFace",
                    "offset": q(5)})))
                print("tree", sc(await call(s, "query_tree_summary", {"doc": doc, "depth": 3})))
            elif PHASE == "s5-setup":
                e = await call(s, "document_create", {"label": "S5SketchOnly"})
                doc = e["structured_content"]["doc"]
                print("doc", doc)
                print("body", brief(await apply(s, doc, "feature_body_create", {"name": "Body"})))
                print("sketch", brief(await apply(s, doc, "sketch_create", {"name": "Sketch", "body": "Body", "plane": "XY"})))
                g, c = rect(20, 30)
                print("geo", brief(await apply(s, doc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": g, "constraints": c})))
                print("tree", sc(await call(s, "query_tree_summary", {"doc": doc, "depth": 3})))
            elif PHASE == "s7-setup":
                e = await call(s, "document_create", {"label": "S7DatumOnly"})
                doc = e["structured_content"]["doc"]
                print("doc", doc)
                print("body", brief(await apply(s, doc, "feature_body_create", {"name": "Body"})))
                print("datum", brief(await apply(s, doc, "feature_datum", {
                    "body": "Body", "name": "DatumPlane", "kind": "plane",
                    "attachment": {"kind": "mapped_name", "object": "XY_Plane"}, "map_mode": "FlatFace",
                    "offset": q(5)})))
                print("tree", sc(await call(s, "query_tree_summary", {"doc": doc, "depth": 3})))

asyncio.run(main())
