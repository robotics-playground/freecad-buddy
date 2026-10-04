"""Close a TC-11 scenario's visual after a proxy restart: python tc11close.py <TAG> <doc-handle|auto>."""
import asyncio
import sys

from tc11lib import Log, Mcp, closing, sc

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main(tag, doc):
    log = Log(f"{tag}-close")
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            if doc == "auto":
                docs = sc(await m.call("document_list", {})).get("documents") or []
                doc = docs[0]["doc"] if docs else None
                log.note(f"doc handles in GUI after proxy restart: {[d.get('label') for d in docs]}")
            await closing(m, log, doc, tag)
    log.save()


asyncio.run(main(sys.argv[1], sys.argv[2]))
