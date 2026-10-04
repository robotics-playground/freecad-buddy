import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
async def main():
    async with lib.Session("tc-07-17") as s:
        H, OBJ = await s.open(lib.GOLD + "/box-10-20-30.FCStd")
        dl = await s.call("document_list", {})
        s.check("given: document_list names the handle", any(d["doc"] == H for d in lib.sc(dl)["documents"]), H)
        open("tc-07-17-handle.txt", "w").write(H)
asyncio.run(main())
