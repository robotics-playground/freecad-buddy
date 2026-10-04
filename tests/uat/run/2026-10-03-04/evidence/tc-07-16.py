import asyncio, json, os, glob, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
async def main():
    for p in glob.glob(lib.EV + "/tc-07-16-fail-*"): os.remove(p)
    async with lib.Session("tc-07-16") as s:
        s.check("given: no failure targets", not glob.glob(lib.EV + "/tc-07-16-fail-*"))
        H, OBJ = await s.open(lib.GOLD + "/box-10-20-30.FCStd")
        calls = [("export_step", {"doc": H, "path": lib.EV + "/tc-07-16-fail-multi.step", "objects": [OBJ, OBJ]}),
                 ("export_step", {"doc": H, "path": lib.EV + "/tc-07-16-fail-unknown.step", "objects": ["NoSuchObject"]}),
                 ("export_stl", {"doc": H, "path": lib.EV + "/tc-07-16-fail-defl.stl", "objects": [OBJ], "linear": 0.00001}),
                 ("export_3mf", {"doc": H, "path": lib.EV + "/tc-07-16-fail-defl.3mf", "objects": [OBJ], "angular": 0.0}),
                 ("export_step", {"doc": H, "path": lib.EV + "/tc-07-16-no-such-dir/x.step", "objects": [OBJ]})]
        envs = [await s.call(t, a) for t, a in calls]
        st = [(e.get("status"), (e.get("detail") or {}).get("message")) for e in envs]
        s.check("every failure non-OK (INVALID_INPUT or RECOMPUTE_ERROR)", all(e.get("status") in ("INVALID_INPUT", "RECOMPUTE_ERROR") for e in envs), st)
        left = glob.glob(lib.EV + "/tc-07-16-fail-*")
        s.check("no file at any failure target", not left, left)
        s.check("no zero-byte stub", not [p for p in left if os.path.getsize(p) == 0], left)
        s.check("missing dir not created", not os.path.exists(lib.EV + "/tc-07-16-no-such-dir"), os.path.exists(lib.EV + "/tc-07-16-no-such-dir"))
        s.check("no export_id minted on failures", not any(lib.sc(e).get("export_id") for e in envs), [lib.sc(e) for e in envs])
        ok = await s.call("export_step", {"doc": H, "path": lib.EV + "/tc-07-16-fail-multi.step", "objects": [OBJ]})
        s.check("later single-object export to same path OK and file exists", ok["status"] == "OK" and os.path.exists(lib.EV + "/tc-07-16-fail-multi.step"), [ok["status"], ok.get("detail")])
asyncio.run(main())
