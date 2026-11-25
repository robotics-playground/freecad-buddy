"""CAP-2 live check for Story 13-9 over MCP (http://127.0.0.1:18765/mcp).

Typed tools only, except step 'bind' which uses script_exec ONLY for the expression binding
(feature_set_expression is Story 13-10, not built yet). Writes a transcript JSON to argv[1].
"""
import asyncio, json, sys, time
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:18765/mcp"
log = []

async def call(s, step, tool, args, note=""):
    t = time.perf_counter()
    r = await s.call_tool(tool, args)
    sc = r.structuredContent or {}
    log.append({"step": step, "tool": tool, "args": args, "note": note, "isError": r.isError,
                "elapsed_s": round(time.perf_counter() - t, 3), "result": sc})
    st = sc.get("status"); d = sc.get("detail") or {}
    print(f"[{step}] {tool} status={st} code={d.get('code')} msg={(d.get('message') or '')[:140]}")
    return sc

def mm(v): return {"value": v, "unit": "mm"}

async def main():
    async with streamable_http_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            log.append({"step": "list", "has_define": "feature_parameters_define" in tools, "has_query": "query_parameters" in tools, "count": len(tools)})
            print("tools", len(tools), "define" , "feature_parameters_define" in tools, "query", "query_parameters" in tools)
            doc = (await call(s, "create", "document_create", {"label": "CAP2d_VarSet"}))["structured_content"]["doc"]
            await call(s, "define", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [
                {"name": "width", "type": "length", "value": mm(20), "description": "plate width"},
                {"name": "height", "type": "length", "value": mm(10)},
                {"name": "shift", "type": "length", "value": mm(5), "group": "Placement"}]})
            await call(s, "body", "feature_body_create", {"doc": doc, "name": "Body"})
            await call(s, "datum", "feature_datum", {"doc": doc, "body": "Body", "name": "Lift", "kind": "plane", "attachment": {"kind": "mapped_name", "object": "XY_Plane"}, "map_mode": "ObjectXY"})
            sk = await call(s, "sketch", "sketch_create", {"doc": doc, "name": "Profile", "face": {"kind": "mapped_name", "object": "Lift", "mapped_name": "Face1"}, "body": "Body"})
            if sk.get("status") != "OK":
                raise SystemExit("sketch on datum refused")
            cons = [{"type": "Coincident", "first": i, "first_pos": 2, "second": (i + 1) % 4, "second_pos": 1} for i in range(4)]
            cons += [{"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2}, {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
                     {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
                     {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": mm(20), "name": "width"},
                     {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": mm(8), "name": "depth"}]
            pts = [(0, 0), (20, 0), (20, 8), (0, 8)]
            geo = [{"kind": "line_segment", "start": list(pts[i]), "end": list(pts[(i + 1) % 4])} for i in range(4)]
            await call(s, "geometry", "sketch_add_geometry", {"doc": doc, "sketch": "Profile", "geometry": geo, "constraints": cons})
            await call(s, "pad", "feature_pad", {"doc": doc, "body": "Body", "profile": "Profile", "name": "Pad", "length": mm(10)})
            code = ("doc = App.ActiveDocument if False else None\n"
                    "import FreeCAD as App\n"
                    "d = [x for x in App.listDocuments().values() if x.Label == 'CAP2d_VarSet'][0]\n"
                    "p = d.getObject('Profile'); pad = d.getObject('Pad')\n"
                    "d.openTransaction('bind expressions')\n"
                    "p.setExpression('Constraints.width', 'Params.width')\n"
                    "pad.setExpression('Length', 'Params.height')\n"
                    "p.setExpression('.AttachmentOffset.Base.x', 'Params.shift')\n"
                    "d.commitTransaction(); d.recompute()\n"
                    "print(sorted(p.ExpressionEngine), pad.ExpressionEngine, pad.Shape.Volume)\n")
            await call(s, "bind", "script_exec", {"doc": doc, "code": code}, note="script_exec used ONLY for expression binding: feature_set_expression is Story 13-10, not built")
            q1 = await call(s, "query1", "query_parameters", {"doc": doc})
            m1 = await call(s, "mass1", "query_mass_properties", {"doc": doc, "object": "Pad"})
            edit = await call(s, "edit", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [
                {"name": "width", "type": "length", "value": mm(30)},
                {"name": "height", "type": "length", "value": mm(15)},
                {"name": "shift", "type": "length", "value": mm(8)}]})
            q2 = await call(s, "query2", "query_parameters", {"doc": doc})
            m2 = await call(s, "mass2", "query_mass_properties", {"doc": doc, "object": "Pad"})
            fp_before = ((edit.get("structured_content") or {}).get("mutation") or {}).get("fingerprint_before")
            await call(s, "undo", "document_undo", {"doc": doc, "expect_fingerprint": fp_before})
            await call(s, "query3", "query_parameters", {"doc": doc})
            await call(s, "mass3", "query_mass_properties", {"doc": doc, "object": "Pad"})
            await call(s, "refuse_unit", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [{"name": "W", "type": "length", "value": mm(3)}]})
            await call(s, "refuse_type", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [{"name": "width", "type": "float", "value": 3.0}]})
            await call(s, "refuse_negative", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [{"name": "width", "type": "length", "value": mm(-1)}]})
            await call(s, "refuse_not_varset", "feature_parameters_define", {"doc": doc, "varset": "Pad", "parameters": [{"name": "x1", "type": "float", "value": 1.0}]})
            await call(s, "query4", "query_parameters", {"doc": doc})
            await call(s, "fit", "view_fit_viewport", {"doc": doc})
    json.dump(log, open(sys.argv[1], "w"), indent=1, default=str)

asyncio.run(main())
