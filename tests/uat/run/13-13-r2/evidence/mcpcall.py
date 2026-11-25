"""Call tools on the container MCP proxy. Usage: mcpcall.py <calls.json> <out.json>

calls.json: list of {"name": optional, "tool": name, "args": {...}} or {"shell": cmd}.
A string arg "$<name>.<dotted path>" is replaced by that field of the named call's
structuredContent (whole-string match keeps the type); "$DOC" by the first document_create handle.
"""

import asyncio
import json
import subprocess
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:18765/mcp"


def lookup(ref, named):
    name, *path = ref[1:].split(".")
    value = named[name]
    for key in path:
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def subst(v, doc, named):
    if isinstance(v, str):
        if v.startswith("$") and v != "$DOC" and v[1:].split(".")[0] in named:
            return lookup(v, named)
        return v.replace("$DOC", doc or "$DOC")
    if isinstance(v, list):
        return [subst(x, doc, named) for x in v]
    if isinstance(v, dict):
        return {k: subst(x, doc, named) for k, x in v.items()}
    return v


async def main(calls_path, out_path):
    calls = json.load(open(calls_path, encoding="utf-8"))
    out, named, doc = [], {}, None
    async with streamablehttp_client(URL, timeout=60, sse_read_timeout=300) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for c in calls:
                if "shell" in c:
                    cp = subprocess.run(
                        [r"C:/Program Files/Git/bin/bash.exe", "-c", c["shell"]],
                        capture_output=True,
                        text=True,
                    )
                    rec = {"shell": c["shell"], "rc": cp.returncode, "out": cp.stdout[-1500:], "err": cp.stderr[-800:]}
                    out.append(rec)
                    print(json.dumps(rec)[:1500])
                    continue
                args = subst(c.get("args", {}), doc, named)
                t0 = time.time()
                res = await s.call_tool(c["tool"], args)
                sc = res.structuredContent
                rec = {
                    "name": c.get("name"),
                    "tool": c["tool"],
                    "args": args,
                    "seconds": round(time.time() - t0, 3),
                    "isError": res.isError,
                    "structuredContent": sc,
                    "text": [b.text for b in res.content if getattr(b, "type", "") == "text"],
                }
                out.append(rec)
                if c.get("name"):
                    named[c["name"]] = sc
                if c["tool"] == "document_create" and doc is None and sc:
                    doc = (sc.get("structured_content") or {}).get("doc") or sc.get("doc")
                print(json.dumps(rec)[:1800])
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1)


asyncio.run(main(sys.argv[1], sys.argv[2]))
