"""CAP-2 live check for Story 13-10 over MCP (http://127.0.0.1:18765/mcp). Typed tools only.

A VarSet drives two sketch constraints, a pad length, the profile sketch's
.AttachmentOffset.Base.z and a datum plane's .AttachmentOffset.Base.z through
feature_set_expression. The VarSet is edited, read back, then every committed call is undone
with document_undo (expect_fingerprint = that call's fingerprint_before).
Writes a transcript JSON to argv[1]. Pauses for screenshots are driven by argv[2] (a flag dir).
"""

import asyncio
import json
import os
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:18765/mcp"
log = []
OUT = sys.argv[1]
FLAGS = sys.argv[2]


def dump():
    with open(OUT, "w") as out:
        json.dump(log, out, indent=1, default=str)


async def pause(name):
    """Write <flags>/<name>.wait and block until <flags>/<name>.go exists (screenshot window)."""
    open(os.path.join(FLAGS, name + ".wait"), "w").close()
    dump()
    print(f"PAUSE {name}", flush=True)
    while not os.path.exists(os.path.join(FLAGS, name + ".go")):
        await asyncio.sleep(1)


async def call(s, step, tool, args, note=""):
    t = time.perf_counter()
    r = await s.call_tool(tool, args)
    sc = r.structuredContent or {}
    log.append({"step": step, "tool": tool, "args": args, "note": note, "isError": r.isError,
                "elapsed_s": round(time.perf_counter() - t, 3), "result": sc,
                "text": [c.text for c in r.content if getattr(c, "text", None)][:1] if not sc else None})
    st = sc.get("status")
    d = sc.get("detail") or {}
    body = sc.get("structured_content") or {}
    m = body.get("mutation") or {}
    print(f"[{step}] {tool} status={st} code={d.get('code')} undo_steps={body.get('undo_steps')} "
          f"rolled_back={m.get('rolled_back')} fp_after={(m.get('fingerprint_after') or {}).get('digest', '')[:12]} "
          f"msg={(d.get('message') or '')[:160]}", flush=True)
    return sc


def mm(v):
    return {"value": v, "unit": "mm"}


def fp_before(env):
    return (((env.get("structured_content") or {}).get("mutation") or {}).get("fingerprint_before") or {})


async def main():
    async with streamable_http_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            log.append({"step": "list", "count": len(tools), "has_set_expression": "feature_set_expression" in tools,
                        "has_define": "feature_parameters_define" in tools, "has_query": "query_parameters" in tools,
                        "has_script_exec": "script_exec" in tools})
            print("tools", len(tools), "set_expression" in str(tools), flush=True)
            doc = (await call(s, "create", "document_create", {"label": "CAP2_Expr_B"}))["structured_content"]["doc"]
            committed = []  # (step, envelope) of every call that added an undo step

            async def mut(step, tool, args, note=""):
                env = await call(s, step, tool, args, note)
                body = env.get("structured_content") or {}
                m = body.get("mutation") or {}
                if env.get("status") == "OK" and m and not m.get("rolled_back") and body.get("undo_steps", 1) != 0:
                    committed.append((step, env))
                return env

            await mut("define", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [
                {"name": "width", "type": "length", "value": mm(20)},
                {"name": "depth", "type": "length", "value": mm(8)},
                {"name": "height", "type": "length", "value": mm(10)},
                {"name": "lift", "type": "length", "value": mm(0)},
                {"name": "datum_z", "type": "length", "value": mm(5)}]})
            await mut("body", "feature_body_create", {"doc": doc, "name": "Body"})
            await mut("sketch", "sketch_create", {"doc": doc, "name": "Profile", "plane": "XY", "body": "Body"})
            cons = [{"type": "Coincident", "first": i, "first_pos": 2, "second": (i + 1) % 4, "second_pos": 1} for i in range(4)]
            cons += [{"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
                     {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
                     {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
                     {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": mm(20), "name": "width"},
                     {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": mm(8), "name": "depth"}]
            pts = [(0, 0), (20, 0), (20, 8), (0, 8)]
            geo = [{"kind": "line_segment", "start": list(pts[i]), "end": list(pts[(i + 1) % 4])} for i in range(4)]
            await mut("geometry", "sketch_add_geometry", {"doc": doc, "sketch": "Profile", "geometry": geo, "constraints": cons})
            await mut("pad", "feature_pad", {"doc": doc, "body": "Body", "profile": "Profile", "name": "Pad", "length": mm(10)})
            tree = await call(s, "tree", "query_tree_summary", {"doc": doc})
            origin_xy = None
            for name in ("XY_Plane", "XY_Plane001"):
                q = await call(s, f"probe_{name}", "query_object", {"doc": doc, "object": name})
                if q.get("status") == "OK":
                    origin_xy = name
                    break
            await mut("datum", "feature_datum", {"doc": doc, "body": "Body", "name": "Datum", "kind": "plane",
                                                 "attachment": {"kind": "mapped_name", "object": origin_xy or "XY_Plane"},
                                                 "offset": mm(5)})
            await call(s, "query0", "query_parameters", {"doc": doc})
            await call(s, "mass0", "query_mass_properties", {"doc": doc, "object": "Pad"})
            await pause("built")

            binds = [
                {"object": "Profile", "path": ".Constraints.width", "expression": "Params.width"},
                {"object": "Profile", "path": ".Constraints.depth", "expression": "Params.depth"},
                {"object": "Pad", "path": "Length", "expression": "Params.height"},
                {"object": "Datum", "path": ".AttachmentOffset.Base.z", "expression": "Params.datum_z"},
            ]
            await mut("bind", "feature_set_expression", {"doc": doc, "expressions": binds})
            await call(s, "query1", "query_parameters", {"doc": doc})
            await call(s, "mass1", "query_mass_properties", {"doc": doc, "object": "Pad"})
            await call(s, "place1", "query_placement", {"doc": doc, "object": "Datum"})

            await mut("edit", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [
                {"name": "width", "type": "length", "value": mm(30)},
                {"name": "depth", "type": "length", "value": mm(12)},
                {"name": "height", "type": "length", "value": mm(15)},
                {"name": "lift", "type": "length", "value": mm(4)},
                {"name": "datum_z", "type": "length", "value": mm(9)}]})
            await call(s, "query2", "query_parameters", {"doc": doc})
            await call(s, "mass2", "query_mass_properties", {"doc": doc, "object": "Pad"})
            await call(s, "place2", "query_placement", {"doc": doc, "object": "Datum"})
            await call(s, "sketch2", "query_sketch_info", {"doc": doc, "sketch": "Profile"})
            await call(s, "fit2", "view_fit_viewport", {"doc": doc})
            await pause("edited")

            # Undo every committed call, newest first, each against its own fingerprint_before.
            log.append({"step": "committed", "steps": [step for step, _ in committed]})
            for step, env in reversed(committed):
                expect = fp_before(env)
                await call(s, f"undo_{step}", "document_undo", {"doc": doc, "expect_fingerprint": expect})
                if step == "edit":
                    await call(s, "q_after_undo_edit", "query_parameters", {"doc": doc})
                    await call(s, "m_after_undo_edit", "query_mass_properties", {"doc": doc, "object": "Pad"})
                    await call(s, "fit_after_undo_edit", "view_fit_viewport", {"doc": doc})
                    await pause("undo_edit")
                if step == "bind":
                    await call(s, "q_after_undo_bind", "query_parameters", {"doc": doc})
                    await call(s, "m_after_undo_bind", "query_mass_properties", {"doc": doc, "object": "Pad"})
            await call(s, "tree_end", "query_tree_summary", {"doc": doc})
            # After the undo chain: no-op, refusals, cycle, then the probe of the leaked transaction.
            # Same text again: a no-op, no transaction.
            await mut("noop", "feature_set_expression", {"doc": doc, "expressions": binds[:2]})
            # Refusals and rollbacks, live.
            await call(s, "refuse_unit", "feature_set_expression", {"doc": doc, "expressions": [
                {"object": "Pad", "path": "Length", "expression": "5 deg"}]})
            await call(s, "refuse_inf", "feature_set_expression", {"doc": doc, "expressions": [
                {"object": "Pad", "path": "Length", "expression": "1 mm / 0"}]})
            await call(s, "refuse_dead_path", "feature_set_expression", {"doc": doc, "expressions": [
                {"object": "Pad", "path": "Length.x", "expression": "Params.height"}]})
            await call(s, "refuse_placement", "feature_set_expression", {"doc": doc, "expressions": [
                {"object": "Datum", "path": ".AttachmentOffset", "expression": "Params.datum_z"}]})
            await call(s, "refuse_long", "feature_set_expression", {"doc": doc, "expressions": [
                {"object": "Pad", "path": "Length", "expression": "+".join(["1"] * 1000)}]})
            await call(s, "cycle", "feature_set_expression", {"doc": doc, "expressions": [
                {"object": "Pad", "path": "Length", "expression": "Pad.Length + 1 mm"}]})
            await call(s, "query3", "query_parameters", {"doc": doc})
            await call(s, "mass3", "query_mass_properties", {"doc": doc, "object": "Pad"})

            await call(s, "undo_after_cycle", "document_undo", {"doc": doc})
            await call(s, "undo_after_cycle_2", "document_undo", {"doc": doc})
            await call(s, "fit_end", "view_fit_viewport", {"doc": doc})
            await pause("start")
            await call(s, "close", "document_close", {"doc": doc})
    dump()
    print("DONE", flush=True)


asyncio.run(main())
