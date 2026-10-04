import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P = {f: lib.EV + f"/tc-07-18-x.{f}" for f in ("step", "stl", "3mf")}
async def main():
    for p in P.values():
        if os.path.exists(p): os.remove(p)
    async with lib.Session("tc-07-18") as s:
        H, OBJ = await s.open(lib.GOLD + "/box-10-20-30.FCStd")
        E = {}
        for f in P:
            e = await s.call(f"export_{f}", {"doc": H, "path": P[f], "objects": [OBJ]}); E[f] = lib.sc(e).get("export_id")
        size0 = {f: os.path.getsize(p) for f, p in P.items()}
        s.check("given: three exports OK", all(E.values()), [E, size0])
        crossed = [("step", "stl"), ("step", "3mf"), ("stl", "step"), ("stl", "3mf"), ("3mf", "step"), ("3mf", "stl")]
        envs = {}
        for v, f in crossed:
            envs[(v, f)] = await s.call(f"verify_export_{v}", {"doc": H, "export_id": E[f]})
        s.check("all six crossed INVALID_INPUT", all(e.get("status") == "INVALID_INPUT" for e in envs.values()), {f"{v}<-{f}": e.get("status") for (v, f), e in envs.items()})
        m = lambda v, f: (envs[(v, f)].get("detail") or {}).get("message")
        s.check("step verifier on STL id message", m("step", "stl") == f"export_id {E['stl']} is not a step export", m("step", "stl"))
        s.check("stl verifier on STEP id message", m("stl", "step") == f"export_id {E['step']} is not a stl export", m("stl", "step"))
        s.check("3mf verifier on STL id message", m("3mf", "stl") == f"export_id {E['stl']} is not a 3mf export", m("3mf", "stl"))
        s.check("crossed envelopes carry no checks", not any(lib.sc(e).get("checks") for e in envs.values()), [lib.sc(e) for e in envs.values()])
        own = {f: await s.call(f"verify_export_{f}", {"doc": H, "export_id": E[f]}) for f in P}
        s.check("matched pairings OK", all(e.get("status") == "OK" for e in own.values()), {f: e.get("status") for f, e in own.items()})
        size1 = {f: os.path.getsize(p) for f, p in P.items()}
        import trimesh
        mm = trimesh.load(P["stl"])
        s.check("sizes unchanged and trimesh True ~6000", size0 == size1 and mm.is_watertight and abs(mm.volume - 6000) < 1, [size0, size1, mm.is_watertight, mm.volume])
        open("tc-07-18-handle.txt", "w").write(H)
asyncio.run(main())
