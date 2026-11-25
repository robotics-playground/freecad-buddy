"""Call tools on the container MCP proxy. Usage: mcpcall.py <calls.json> <out.json>
calls.json: list of {"tool": name, "args": {...}}; "$DOC" in a string arg is replaced by the handle
returned by the first document_create."""
import asyncio, json, sys, time
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:18765/mcp"

def subst(v, doc):
    if isinstance(v, str):
        return v.replace("$DOC", doc or "$DOC")
    if isinstance(v, list):
        return [subst(x, doc) for x in v]
    if isinstance(v, dict):
        return {k: subst(x, doc) for k, x in v.items()}
    return v

async def main(calls_path, out_path):
    calls = json.load(open(calls_path, encoding="utf-8"))
    out = []
    doc = None
    async with streamablehttp_client(URL, timeout=60, sse_read_timeout=300) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for c in calls:
                if "shell" in c:
                    import subprocess
                    cp = subprocess.run([r"C:/Program Files/Git/bin/bash.exe", "-c", c["shell"]], capture_output=True, text=True)
                    rec = {"shell": c["shell"], "rc": cp.returncode, "out": cp.stdout[-800:], "err": cp.stderr[-800:]}
                    out.append(rec); print(json.dumps(rec)[:1200]); continue
                args = subst(c.get("args", {}), doc)
                t0 = time.time()
                res = await s.call_tool(c["tool"], args)
                rec = {"tool": c["tool"], "args": args, "seconds": round(time.time() - t0, 3),
                       "isError": res.isError,
                       "structuredContent": res.structuredContent,
                       "text": [b.text for b in res.content if getattr(b, "type", "") == "text"]}
                out.append(rec)
                if c["tool"] == "document_create" and doc is None and res.structuredContent:
                    sc = res.structuredContent
                    doc = (sc.get("structured_content") or {}).get("doc") or sc.get("doc")
                print(json.dumps(rec)[:1500])
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1)

asyncio.run(main(sys.argv[1], sys.argv[2]))
