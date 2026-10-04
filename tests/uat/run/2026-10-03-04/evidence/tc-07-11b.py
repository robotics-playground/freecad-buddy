import asyncio, json, os, glob, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
async def main():
    H = open("tc-07-11-handle.txt").read().strip(); OBJ = "Box"
    async with lib.Session("tc-07-11") as s:
        t0 = await s.call("query_tree_summary", {"doc": H})
        envs = {}
        for tool, x in (("export_step", "step"), ("export_stl", "stl"), ("export_3mf", "3mf")):
            envs[tool] = await s.call(tool, {"doc": H, "path": lib.EV + f"/tc-07-11-multi.{x}", "objects": [OBJ, OBJ]})
        s.check("all three INVALID_INPUT", all(e.get("status") == "INVALID_INPUT" for e in envs.values()), {k: e.get("status") for k, e in envs.items()})
        msgs = {k: (e.get("detail") or {}).get("message") for k, e in envs.items()}
        s.check("message 'export supports a single object; got multiple'", all(m == "export supports a single object; got multiple" for m in msgs.values()), msgs)
        left = glob.glob(lib.EV + "/tc-07-11-multi.*")
        s.check("no partial file", not left, left)
        u = await s.call("export_step", {"doc": H, "path": lib.EV + "/tc-07-11-unknown.step", "objects": ["NoSuchObject"]})
        s.check("unknown object -> INVALID_INPUT 'unknown object: NoSuchObject'", u.get("status") == "INVALID_INPUT" and (u.get("detail") or {}).get("message") == "unknown object: NoSuchObject" and not os.path.exists(lib.EV + "/tc-07-11-unknown.step"), [u.get("status"), (u.get("detail") or {}).get("message")])
        d = await s.call("document_create", {"label": "tc07_empty"}); HE = lib.sc(d)["doc"]
        em = await s.call("export_step", {"doc": HE, "path": lib.EV + "/tc-07-11-empty.step"})
        s.check("empty doc -> INVALID_INPUT 'document has no objects to export'", em.get("status") == "INVALID_INPUT" and (em.get("detail") or {}).get("message") == "document has no objects to export" and not os.path.exists(lib.EV + "/tc-07-11-empty.step"), [em.get("status"), (em.get("detail") or {}).get("message")])
        await s.call("document_close", {"doc": HE})
        t1 = await s.call("query_tree_summary", {"doc": H})
        s.check("tree unchanged by refusals", lib.sc(t0).get("tree") == lib.sc(t1).get("tree"), [lib.sc(t0).get("tree"), lib.sc(t1).get("tree")])
asyncio.run(main())
