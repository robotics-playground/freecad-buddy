import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P = lib.EV + "/tc-07-17-stale.stl"
async def main():
    H = open("tc-07-17-handle.txt").read().strip()
    if os.path.exists(P): os.remove(P)
    async with lib.Session("tc-07-17") as s:
        envs = [await s.call(t, {"doc": H, "export_id": "fcb-export:bogus"}) for t in ("verify_export_step", "verify_export_stl", "verify_export_3mf")]
        s.check("three unknown-id calls INVALID_INPUT", all(e.get("status") == "INVALID_INPUT" for e in envs), [e.get("status") for e in envs])
        s.check("message 'unknown or stale export_id: fcb-export:bogus'", all((e.get("detail") or {}).get("message") == "unknown or stale export_id: fcb-export:bogus" for e in envs), [(e.get("detail") or {}).get("message") for e in envs])
        s.check("detail.data.exception == ValidationError", all(((e.get("detail") or {}).get("data") or {}).get("exception") == "ValidationError" for e in envs), [((e.get("detail") or {}).get("data") or {}).get("exception") for e in envs])
        em = await s.call("verify_export_step", {"doc": H, "export_id": ""})
        s.check("empty export_id -> INVALID_INPUT 'missing required 'export_id''", em.get("status") == "INVALID_INPUT" and (em.get("detail") or {}).get("message") == "missing required 'export_id'", [em.get("status"), (em.get("detail") or {}).get("message"), em.get("_raw")])
        e = await s.call("export_stl", {"doc": H, "path": P, "objects": ["Box"]}); EID = lib.sc(e).get("export_id")
        await s.call("document_close", {"doc": H})
        o = await s.call("document_open", {"path": lib.GOLD + "/box-10-20-30.FCStd"}); H2 = lib.sc(o)["doc"]; print("H", H, "H2", H2, "same handle?", H == H2)
        r = await s.call("verify_export_stl", {"doc": H2, "export_id": EID})
        msg = (r.get("detail") or {}).get("message", "")
        s.check("reopened-handle verify refused: starts 'export_id ' contains 'does not belong to document'", r.get("status") == "INVALID_INPUT" and msg.startswith("export_id ") and "does not belong to document" in msg, [r.get("status"), msg, json.dumps(lib.sc(r))[:300]])
        q = await s.call("query_capabilities", {})
        s.check("no crash: query_capabilities OK", q.get("status") == "OK", q.get("status"))
        import trimesh
        m = trimesh.load(P)
        s.check("outside trimesh: True, volume near 6000", m.is_watertight and abs(m.volume - 6000) < 1, [m.is_watertight, m.volume])
        open("tc-07-17-handle2.txt", "w").write(H2)
asyncio.run(main())
