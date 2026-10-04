import asyncio, json, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def main():
    async with streamablehttp_client(lib.ENDPOINT) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            surf = {}
            for t in tools:
                ann = t.annotations.model_dump() if t.annotations else {}
                props = sorted((t.inputSchema or {}).get("properties", {}).keys())
                surf[t.name] = {"mut": not ann.get("readOnlyHint", False), "annotations": ann, "props": props,
                                "additionalProperties": (t.inputSchema or {}).get("additionalProperties")}
            json.dump(surf, open("tc-07-00-tool_surface.json", "w"), indent=1)
            print("tools:", len(surf))
            print("confirm-declaring:", sorted(k for k, v in surf.items() if "confirm" in v["props"]))
            print("export_* props:", {k: v["props"] for k, v in surf.items() if k.startswith("export_")})
            print("export_* addlProps:", {k: v["additionalProperties"] for k, v in surf.items() if k.startswith("export_")})
            print("mut with confirm & export:", [k for k, v in surf.items() if v["mut"] and "confirm" in v["props"] and k.startswith("export_")])
asyncio.run(main())
