"""TC-05-14 driver. Phase 'setup' builds the Given; phase 'when' runs the refused undos; phase 'probe' re-reads state."""
import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVID = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-04-01/evidence"
LOG = open(f"{EVID}/tc-05-14-mcp.jsonl", "a", encoding="utf-8")


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
    LOG.write(json.dumps({"phase": sys.argv[1], "tool": tool, "args": args, "envelope": env}) + "\n")
    LOG.flush()
    return env


async def apply(s, doc, tool, args):
    p = await call(s, "preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": args}})
    tok = (p.get("structured_content") or {}).get("preview_id")
    return await call(s, tool, dict(args, doc=doc, confirm={"preview_id": tok}))


def brief(e):
    sc = e.get("structured_content") or {}
    return {"status": e.get("status"), "detail": e.get("detail") and {k: e["detail"].get(k) for k in ("code", "message")},
            "text": e.get("text")}


async def main():
    phase = sys.argv[1]
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if phase == "setup":
                print("list", json.dumps(brief(await call(s, "document_list", {}))))
                doc = (await call(s, "document_create", {"label": "TC0514"}))["structured_content"]["doc"]
                print("doc", doc)
                print("body", brief(await apply(s, doc, "feature_body_create", {"name": "Body"})))
                print("sketch", brief(await apply(s, doc, "sketch_create", {"name": "Sketch", "body": "Body", "plane": "XY"})))
                g, c = rect(20, 20)
                print("geo", brief(await apply(s, doc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": g, "constraints": c})))
                si = await call(s, "query_sketch_info", {"doc": doc, "sketch": "Sketch"})
                print("sketch_info", {k: si["structured_content"].get(k) for k in ("fully_constrained", "dof")})
                pad = await apply(s, doc, "feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)})
                m = pad.get("structured_content", {}).get("mutation") or {}
                print("pad", brief(pad))
                print("fp_before", json.dumps(m.get("fingerprint_before")))
                print("fp_after", json.dumps(m.get("fingerprint_after")))
                print("fit", brief(await call(s, "view_fit_viewport", {"doc": doc})))
            else:
                doc = sys.argv[2]
                mp = await call(s, "query_mass_properties", {"doc": doc, "object": "Pad"})
                print("mass Pad", json.dumps(mp.get("structured_content"))[:400])
                tr = await call(s, "query_tree_summary", {"doc": doc, "depth": 3})
                print("tree", json.dumps(tr.get("structured_content"))[:1500])
                if phase == "when":
                    u1 = await call(s, "document_undo", {"doc": doc, "expect_fingerprint": {"objects": [], "digest": "0" * 64}})
                    print("undo1", json.dumps(u1)[:1500])
                    u2 = await call(s, "document_undo", {"doc": doc, "expect_fingerprint": {"digest": "abc"}})
                    print("undo2", json.dumps(u2)[:1500])
                    mp = await call(s, "query_mass_properties", {"doc": doc, "object": "Pad"})
                    print("mass Pad after", json.dumps(mp.get("structured_content"))[:400])
                    tr = await call(s, "query_tree_summary", {"doc": doc, "depth": 3})
                    print("tree after", json.dumps(tr.get("structured_content"))[:1500])
                    print("fit", brief(await call(s, "view_fit_viewport", {"doc": doc})))
                    print("list", json.dumps((await call(s, "document_list", {})).get("structured_content")))

asyncio.run(main())
