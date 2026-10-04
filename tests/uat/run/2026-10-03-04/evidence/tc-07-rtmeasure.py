"""Bridge-side measure + MCP fit of a document the FreeCAD GUI imported (File > Open) from an export.
usage: tc-07-rtmeasure.py <tag> <doc-handle>"""
import asyncio, sys, json, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
async def main():
    tag, H = sys.argv[1:3]
    async with lib.Session(tag) as s:
        t = await s.call("query_tree_summary", {"doc": H}); tree = lib.sc(t).get("tree") or []
        print("RT tree", tree)
        for n in tree:
            m = await s.call("query_mass_properties", {"doc": H, "object": n["name"]})
            print("RT mass", n["name"], m.get("status"), json.dumps(lib.sc(m).get("volume")), (m.get("detail") or {}).get("message"))
        f = await s.call("view_fit_viewport", {"doc": H})
        print("RT view_fit_viewport", f.get("status"), json.dumps(lib.sc(f) or f.get("detail"))[:300])
asyncio.run(main())
