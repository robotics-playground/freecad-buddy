"""TC-02-15 inline-host leg: stdio MCP to `freecad_buddy.hosts.main serve --transport stdio --mode inline` under FCB_PYTHON."""
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FCB = os.path.expandvars(r"%USERPROFILE%\micromamba\envs\fcb")
env = dict(os.environ)
env["PYTHONPATH"] = ";".join([rf"{FCB}\Library\bin", rf"{FCB}\Library\lib", r"D:\Work\Personal\Sources\freecad-buddy\src"])
env["PATH"] = rf"{FCB}\Library\bin;" + env["PATH"]
env["PYTHONUTF8"] = "1"

async def main():
    params = StdioServerParameters(command=rf"{FCB}\python.exe", args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            caps = await s.call_tool("query_capabilities", {})
            ctext = "".join(b.text for b in caps.content if hasattr(b, "text"))
            print("caps:", json.loads(ctext).get("structured_content", {}).get("freecad_version"))
            res = await s.call_tool("query_tree_summary", {"doc": 12345})
            text = "".join(b.text for b in res.content if hasattr(b, "text"))
            print("isError:", res.isError)
            print("result:", text[:800])

asyncio.run(main())
