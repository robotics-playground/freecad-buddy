"""Harness E2E smoke over the live :8765 bridge. Usage: e2e.py <run_tag> <out_dir>"""
import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG, OUT = sys.argv[1], sys.argv[2]
rows = []

def rec(name, ok, detail=""):
    rows.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:28} {detail}", flush=True)

async def call(s, tool, args):
    res = await s.call_tool(tool, args)
    text = "".join(b.text for b in res.content if hasattr(b, "text"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"status": "NO_JSON", "_raw": text[:300]}

async def mutate(s, doc, tool, args):
    pv = await call(s, "preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": args}, "render": "off"})
    pid = (pv.get("structured_content") or {}).get("preview_id")
    if not pid:
        rec(f"preview:{tool}", False, f"{pv.get('status')} {pv.get('detail')}")
        return pv
    env = await call(s, tool, {"doc": doc, **args, "confirm": {"preview_id": pid, "elicitation_action": "accept"}})
    rec(f"apply:{tool}", env.get("status") == "OK", f"{env.get('status')} {env.get('detail') or ''}"[:120])
    return env

def line(a, b):
    return {"kind": "line_segment", "start": a, "end": b}

async def main():
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            cap = (await call(s, "query_capabilities", {})).get("structured_content", {})
            rec("capabilities", bool(cap.get("freecad_version")), f"fc={cap.get('freecad_version')}")
            cr = await call(s, "document_create", {"label": f"harness_{TAG}"})
            rec("document_create", cr.get("status") == "OK", cr.get("status"))
            doc = cr["structured_content"]["doc"]
            await mutate(s, doc, "feature_body_create", {"name": "Body"})
            await mutate(s, doc, "sketch_create", {"name": "Profile", "plane": "XY", "body": "Body"})
            mm = lambda v: {"value": v, "unit": "mm"}
            await mutate(s, doc, "sketch_add_geometry", {"sketch": "Profile", "geometry": [
                line([0, 0], [20, 0]), line([20, 0], [20, 10]), line([20, 10], [0, 10]), line([0, 10], [0, 0])],
                "constraints": [
                {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
                {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
                {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1},
                {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
                {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
                {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
                {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
                {"type": "DistanceX", "first": 0, "value": mm(20)},
                {"type": "DistanceY", "first": 1, "value": mm(10)}]})
            await mutate(s, doc, "feature_pad", {"body": "Body", "profile": "Profile", "name": "Plate",
                                                  "length": {"value": 5, "unit": "mm"}})
            mp = (await call(s, "query_mass_properties", {"doc": doc, "object": "Plate"})).get("structured_content", {})
            vol = (mp.get("volume") or {}).get("value")
            rec("mass Plate == 1000 mm3", vol is not None and abs(vol - 1000) < 1e-3, f"vol={vol}")
            vs = await call(s, "verify_shape", {"doc": doc, "object": "Plate"})
            rec("verify_shape", vs.get("status") == "OK", vs.get("status"))
            vr = await call(s, "verify_recompute", {"doc": doc})
            rec("verify_recompute", vr.get("status") == "OK", vr.get("status"))
            ex = await call(s, "export_step", {"doc": doc, "path": f"{OUT}/{TAG}-plate.step", "objects": ["Plate"]})
            eid = (ex.get("structured_content") or {}).get("export_id")
            rec("export_step", ex.get("status") == "OK" and bool(eid), f"{ex.get('status')} {ex.get('detail') or ''}"[:120])
            if eid:
                ve = await call(s, "verify_export_step", {"doc": doc, "export_id": eid})
                rec("verify_export_step", ve.get("status") == "OK", f"{ve.get('status')} {ve.get('detail') or ''}"[:120])
            fit = await call(s, "view_fit_viewport", {"doc": doc})
            rec("view_fit_viewport", fit.get("status") == "OK", fit.get("status"))
            sh = await call(s, "query_screenshot", {"doc": doc, "view": {"camera": "iso"}})
            sc = sh.get("structured_content") or {}
            rec("query_screenshot", sh.get("status") == "OK", json.dumps({k: sc.get(k) for k in ("artifact", "path", "image", "scene") if k in sc})[:300])
            print(f"DOC {doc}")
    print(f"{sum(rows)}/{len(rows)} passed")
    return 0 if all(rows) else 1

sys.exit(asyncio.run(main()))
