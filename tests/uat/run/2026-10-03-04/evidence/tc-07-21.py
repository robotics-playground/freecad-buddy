import asyncio, json, os, copy, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P = {f: lib.EV + f"/tc-07-21-pair.{f}" for f in ("step", "stl", "3mf")}
CLOSED = {"OK", "SPEC_FAILED", "RECOMPUTE_ERROR", "TIMEOUT", "OOM_KILLED", "WORKER_CRASHED", "INVALID_INPUT"}
async def main():
    for p in P.values():
        if os.path.exists(p): os.remove(p)
    async with lib.Session("tc-07-21") as s:
        s.check("given: no stale targets", not any(os.path.exists(p) for p in P.values()))
        H, OBJ = await s.open(lib.GOLD + "/box-10-20-30.FCStd")
        W = {f: await s.call(f"export_{f}", {"doc": H, "path": P[f], "objects": [OBJ]}) for f in P}
        V = {f: await s.call(f"verify_export_{f}", {"doc": H, "export_id": lib.sc(W[f]).get("export_id")}) for f in P}
        s.check("every write verified false", all(lib.sc(w).get("verified") is False for w in W.values()), {f: lib.sc(w).get("verified") for f, w in W.items()})
        s.check("each write text ends 'export written -> <path>.'", all((w.get("text") or "").endswith(f"export written -> {P[f]}.") for f, w in W.items()), {f: w.get("text") for f, w in W.items()})
        s.check("write results carry no checks", not any("checks" in lib.sc(w) for w in W.values()), {f: list(lib.sc(w)) for f, w in W.items()})
        s.check("verify schema fcb.validation-report/1 vs write fcb.result-envelope/1", all(lib.sc(v).get("schema") == "fcb.validation-report/1" for v in V.values()) and all(w.get("schema") == "fcb.result-envelope/1" for w in W.values()), [{f: lib.sc(v).get("schema") for f, v in V.items()}, {f: w.get("schema") for f, w in W.items()}])
        s.check("verify verdict OK and every check passed", all(lib.sc(v).get("verdict") == "OK" and all(c["passed"] for c in lib.sc(v).get("checks", [])) for v in V.values()), {f: [lib.sc(v).get("verdict"), [c["id"] for c in lib.sc(v).get("checks", []) if not c["passed"]]] for f, v in V.items()})
        before = copy.deepcopy(W["stl"])
        open(P["stl"], "r+b").truncate(0)
        v0 = await s.call("verify_export_stl", {"doc": H, "export_id": lib.sc(W["stl"]).get("export_id")})
        s.check("after truncating STL to 0 B: write result unchanged, verify non-OK", W["stl"] == before and v0.get("status") != "OK", [v0.get("status"), (v0.get("detail") or {}).get("message"), os.path.getsize(P["stl"])])
        seen = [w.get("status") for w in W.values()] + [v.get("status") for v in V.values()] + [v0.get("status")]
        s.check("status set closed across calls", all(x in CLOSED for x in seen), seen)
        open("tc-07-21-handle.txt", "w").write(H)
asyncio.run(main())
