"""TC-07-03 literal When: document_create, sketch_create XY, sketch_add_geometry one unconstrained line."""
import asyncio, json, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
async def mutate(s, H, tool, args):
    p = await s.call("preview_dry_run", {"doc": H, "operation": {"tool": tool, "args": args}, "render": "off"})
    pid = lib.sc(p).get("preview_id")
    print("preview", tool, p.get("status"), (p.get("detail") or "")) 
    return await s.call(tool, {"doc": H, **args, "confirm": {"preview_id": pid, "elicitation_action": "accept"}})
async def main():
    async with lib.Session("tc-07-03") as s:
        d = await s.call("document_create", {"label": "tc07_sketch"})
        s.check("given: document_create OK", d["status"] == "OK", d["status"])
        H = lib.sc(d)["doc"]; open("tc-07-03-handle.txt", "w").write(H)
        sk = await mutate(s, H, "sketch_create", {"name": "Sketch", "plane": "XY"})
        s.check("sketch_create OK", sk["status"] == "OK", [sk["status"], sk.get("detail")])
        g = await mutate(s, H, "sketch_add_geometry", {"sketch": "Sketch", "geometry": [{"kind": "line_segment", "start": [0, 0], "end": [10, 0]}]})
        print(json.dumps({k: g.get(k) for k in ("status", "detail", "text")})[:1500])
        print(json.dumps(lib.sc(g))[:1500])
        v = await s.call("verify_sketch", {"doc": H, "sketch": "Sketch"})
        print("verify_sketch after literal add:", v["status"], json.dumps(lib.sc(v))[:800])
asyncio.run(main())
