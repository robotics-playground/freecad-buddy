"""usage: mcpcall.py <step-label> <tool> '<json args>'  -> prints and saves the result."""
import asyncio, json, sys, pathlib
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVID = pathlib.Path(r"D:\Work\Personal\Sources\fcb-verify-13-11\tests\uat\run\13-11-r1\evidence")

async def main(label, tool, args):
    async with streamablehttp_client("http://127.0.0.1:18765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if tool == "__list__":
                tools = await s.list_tools()
                return {"tools": [t.name for t in tools.tools]}
            res = await s.call_tool(tool, args)
            out = res.structuredContent
            if out is None:
                out = {"content": [getattr(c, "text", str(c)) for c in res.content]}
            out = {"isError": res.isError, "result": out}
            return out

label, tool = sys.argv[1], sys.argv[2]
args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
out = asyncio.run(main(label, tool, args))
text = json.dumps({"tool": tool, "args": args, **out}, indent=1, default=str)
(EVID / f"{label}.json").write_text(text, encoding="utf-8")
print(text)
