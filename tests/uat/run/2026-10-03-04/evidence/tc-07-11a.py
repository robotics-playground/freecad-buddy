import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
async def main():
    for x in ("step", "stl", "3mf"):
        p = lib.EV + f"/tc-07-11-multi.{x}"
        if os.path.exists(p): os.remove(p)
    async with lib.Session("tc-07-11") as s:
        s.check("given: no stale targets", not any(os.path.exists(lib.EV + f"/tc-07-11-multi.{x}") for x in ("step", "stl", "3mf")))
        H, OBJ = await s.open(lib.GOLD + "/box-10-20-30.FCStd"); print(H, OBJ)
        open("tc-07-11-handle.txt", "w").write(H)
asyncio.run(main())
