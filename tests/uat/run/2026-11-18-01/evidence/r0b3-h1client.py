"""H1 stdio client for TC-11-01 / TC-11-17 (run R0b-3). Talks only to a child H1 host, never to a proxy."""
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

mode = sys.argv[1]  # on | off
tag = "tc-11-01" if mode == "on" else "tc-11-17"
run = "/repo/tests/uat/run/2026-11-18-01/evidence"
env = dict(os.environ)
for k in ("FREECAD_BUDDY_SCRIPT_EXEC", "FREECAD_BUDDY_UNATTENDED", "FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED"):
    env.pop(k, None)
if mode == "off":
    env["FREECAD_BUDDY_SCRIPT_EXEC"] = "0"
env["FREECAD_BUDDY_AUDIT_LOG"] = f"{run}/r0b3-{tag}-audit.jsonl"
code = "result = len(doc.Objects)" if mode == "on" else "doc.addObject('Part::Box', 'Leak'); doc.recompute()"

def show(name, res):
    print("##", name, "isError=", res.isError)
    print("   structured:", json.dumps(res.structuredContent)[:900] if res.structuredContent else None)
    print("   text:", [getattr(c, "text", None) for c in res.content][:1])

async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"], env=env)
    errlog = open(f"{run}/r0b3-{tag}-h1.stderr.log", "w")
    async with stdio_client(params, errlog=errlog) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            names = [t.name for t in tools.tools]
            print("H1 tools/list length", len(names), "script_exec listed", "script_exec" in names)
            c = await s.call_tool("document_create", {"label": tag.replace("-", "")})
            show("document_create", c)
            h = c.structuredContent["structured_content"]["doc"]
            e = await s.call_tool("script_exec", {"doc": h, "code": code})
            show("script_exec", e)
            if mode == "off":
                t = await s.call_tool("query_tree_summary", {"doc": h})
                show("query_tree_summary", t)
            q = await s.call_tool("query_capabilities", {})
            print("H1 exec_enabled", q.structuredContent["structured_content"]["exec_enabled"])
asyncio.run(main())
