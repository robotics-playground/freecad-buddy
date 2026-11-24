"""Round 2 live check over MCP: RT1 no-op define with a user Box, and script_exec errors (RT4)."""
import asyncio, json, sys, time
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
URL = "http://127.0.0.1:18765/mcp"
log = []
async def call(s, step, tool, args):
    t = time.perf_counter()
    r = await s.call_tool(tool, args)
    sc = r.structuredContent or {}
    log.append({"step": step, "tool": tool, "args": args, "isError": r.isError, "elapsed_s": round(time.perf_counter() - t, 3), "result": sc})
    d = sc.get("detail") or {}
    c = sc.get("structured_content") or {}
    print(f"[{step}] {tool} status={sc.get('status')} code={d.get('code')!r} msg={(d.get('message') or '')[:110]} | " + json.dumps({k: c.get(k) for k in ('added','updated','unchanged','undo_steps','undone','matches_pre_op','stdout') if k in c})[:300])
    return sc
BOX = ("import FreeCAD as App\n"
       "d = [x for x in App.listDocuments().values() if x.Label == 'RT1_Box'][0]\n"
       "d.openTransaction('user box'); d.addObject('Part::Box', 'UserBox'); d.commitTransaction(); d.recompute()\n"
       "print('UndoCount', d.UndoCount, 'UserBox', d.getObject('UserBox') is not None)\n")
PROBE = ("import FreeCAD as App\n"
         "d = [x for x in App.listDocuments().values() if x.Label == 'RT1_Box'][0]\n"
         "v = d.getObject('Params')\n"
         "print('UndoCount', d.UndoCount, 'UserBox', d.getObject('UserBox') is not None, 'note', repr(v.note) if v else None)\n")
async def main():
    async with streamable_http_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            doc = (await call(s, "create", "document_create", {"label": "RT1_Box"}))["structured_content"]["doc"]
            note = [{"name": "note", "type": "string", "value": "rev A"}, {"name": "width", "type": "length", "value": {"value": 12, "unit": "mm"}}]
            await call(s, "define1", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": note})
            await call(s, "user_box", "script_exec", {"doc": doc, "code": BOX})
            await call(s, "define_noop", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": note})
            await call(s, "probe_after_noop", "script_exec", {"doc": doc, "code": PROBE})
            await call(s, "define_partial", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [note[0], {"name": "width", "type": "length", "value": {"value": 14, "unit": "mm"}}]})
            await call(s, "undo_partial", "document_undo", {"doc": doc})
            await call(s, "probe_after_partial_undo", "script_exec", {"doc": doc, "code": PROBE})
            await call(s, "define_noop2", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": note})
            await call(s, "undo_after_noop", "document_undo", {"doc": doc})
            await call(s, "probe_after_noop_undo", "script_exec", {"doc": doc, "code": PROBE})
            await call(s, "meta_change", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [{"name": "note", "type": "string", "value": "rev B", "group": "Other"}]})
            await call(s, "nul_string", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [{"name": "tag", "type": "string", "value": "rev A\u0000x"}]})
            await call(s, "varset_W", "feature_parameters_define", {"doc": doc, "varset": "W", "parameters": [{"name": "x1", "type": "float", "value": 1.0}]})
            await call(s, "shape_name", "feature_parameters_define", {"doc": doc, "varset": "Params", "parameters": [{"name": "Shape", "type": "float", "value": 1.0}]})
            await call(s, "exec_oserror", "script_exec", {"doc": doc, "code": "raise OSError(5, 'access denied')"})
            await call(s, "exec_code_method", "script_exec", {"doc": doc, "code": "class E(Exception):\n    def code(self):\n        return 1\nraise E('boom')"})
            await call(s, "query", "query_parameters", {"doc": doc})
    json.dump(log, open(sys.argv[1], "w"), indent=1, default=str)
asyncio.run(main())
