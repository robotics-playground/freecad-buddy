import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P = lib.EV + "/tc-07-12-default-multi.step"
async def main():
    async with lib.Session("tc-07-12") as s:
        o = await s.call("document_open", {"path": lib.EV + "/tc-07-12-two-objects.FCStd"}); H3 = lib.sc(o)["doc"]
        t = await s.call("query_tree_summary", {"doc": H3}); print(lib.sc(t).get("tree"))
        e = await s.call("export_step", {"doc": H3, "path": P})
        m = (e.get("detail") or {}).get("message")
        s.check("supplementary: genuine 2-object doc -> INVALID_INPUT multiple-objects message, no file", e.get("status") == "INVALID_INPUT" and m == "document has multiple objects; specify 'objects' with the one to export" and not os.path.exists(P), [e.get("status"), m, os.path.exists(P)])
        await s.call("document_close", {"doc": H3})
asyncio.run(main())
