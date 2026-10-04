"""TC-08-06 driver. Phase 'setup' builds the Given; phase 'when' runs pad/undo pairs; 'probe' re-reads state; 'close' cleans up."""
import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVID = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-04-01/evidence"
LOG = open(f"{EVID}/tc-08-06-mcp.jsonl", "a", encoding="utf-8")


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
    return {"status": e.get("status"), "detail": e.get("detail") and {k: e["detail"].get(k) for k in ("code", "message")},
            "text": e.get("text")}


def undo_view(e):
    sc = e.get("structured_content") or {}
    keys = ("undone", "fingerprint_before", "fingerprint_after", "matches_pre_op", "restored_objects", "undo_count", "errors")
    return {"status": e.get("status"), "detail": e.get("detail"), "text": e.get("text"), **{k: sc.get(k) for k in keys}}


async def tree(s, doc):
    tr = await call(s, "query_tree_summary", {"doc": doc, "depth": 3})
    return json.dumps(tr.get("structured_content"))[:1500]


PAD = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)}


async def main():
    phase = sys.argv[1]
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if phase == "setup":
                print("list", json.dumps(brief(await call(s, "document_list", {}))))
                doc = (await call(s, "document_create", {"label": "TC0806"}))["structured_content"]["doc"]
                print("doc", doc)
                print("body", brief(await apply(s, doc, "feature_body_create", {"name": "Body"})))
                print("sketch", brief(await apply(s, doc, "sketch_create", {"name": "Sketch", "body": "Body", "plane": "XY"})))
                g, c = rect(20, 20)
                print("geo", brief(await apply(s, doc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": g, "constraints": c})))
                si = await call(s, "query_sketch_info", {"doc": doc, "sketch": "Sketch"})
                print("sketch_info", {k: si["structured_content"].get(k) for k in ("fully_constrained", "dof")})
                # Given check: document_undo is not refused with "undo is unavailable".
                gu = await call(s, "document_undo", {"doc": doc})
                print("given_undo", json.dumps(undo_view(gu)))
                print("geo_reapply", brief(await apply(s, doc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": g, "constraints": c})))
                si = await call(s, "query_sketch_info", {"doc": doc, "sketch": "Sketch"})
                print("sketch_info_2", {k: si["structured_content"].get(k) for k in ("fully_constrained", "dof")})
                print("tree", await tree(s, doc))
                print("fit", brief(await call(s, "view_fit_viewport", {"doc": doc})))
            elif phase == "when":
                doc = sys.argv[2]
                pad1 = await apply(s, doc, "feature_pad", PAD)
                m1 = (pad1.get("structured_content") or {}).get("mutation") or {}
                print("pad1", json.dumps(brief(pad1)))
                print("pad1 fp_before", json.dumps(m1.get("fingerprint_before")))
                print("pad1 fp_after", json.dumps(m1.get("fingerprint_after")))
                digest = m1["fingerprint_before"]["digest"]
                u_str = await call(s, "document_undo", {"doc": doc, "expect_fingerprint": digest})
                print("undo_string", json.dumps(undo_view(u_str)))
                pad2 = await apply(s, doc, "feature_pad", PAD)
                m2 = (pad2.get("structured_content") or {}).get("mutation") or {}
                print("pad2", json.dumps(brief(pad2)))
                print("pad2 fp_before", json.dumps(m2.get("fingerprint_before")))
                u_rec = await call(s, "document_undo", {"doc": doc, "expect_fingerprint": m2["fingerprint_before"]})
                print("undo_record", json.dumps(undo_view(u_rec)))
                pad3 = await apply(s, doc, "feature_pad", PAD)
                print("pad3", json.dumps(brief(pad3)))
                u_42 = await call(s, "document_undo", {"doc": doc, "expect_fingerprint": 42})
                print("undo_42", json.dumps(undo_view(u_42)))
                print("tree_after_42", await tree(s, doc))
                u_none = await call(s, "document_undo", {"doc": doc})
                print("undo_none", json.dumps(undo_view(u_none)))
                print("tree_final", await tree(s, doc))
                print("fit", brief(await call(s, "view_fit_viewport", {"doc": doc})))
            elif phase == "close":
                print("close", brief(await call(s, "document_close", {"doc": sys.argv[2]})))
                print("list", json.dumps(brief(await call(s, "document_list", {}))))

asyncio.run(main())
