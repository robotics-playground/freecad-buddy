"""RT-2 proof: run every `script_exec { doc: <handle>, code: "..." }` call that the fix round changed,
copied from TC-12, TC-13 and test-plan.md, against the first open document of the container FreeCAD.

Run in the container: docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/run/2026-11-18-10-10-proof/run-script-exec-sites.py
"""

import asyncio
import glob
import json
import os
import re

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

PATTERN = re.compile(r'script_exec \{ doc: <handle>, code: "([^"]*)" \}')


def sites():
    paths = [glob.glob(f"/repo/tests/uat/testcases/TC-{n}*.md")[0] for n in ("12", "13")]
    paths.append("/repo/tests/uat/test-plan.md")
    for path in paths:
        text = open(path, encoding="utf-8").read().replace("\n", " ")
        for match in PATTERN.finditer(text):
            yield os.path.basename(path)[:6], match.group(1)


async def main():
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listing = await session.call_tool("document_list", {})
            documents = json.loads(listing.content[0].text)["structured_content"]["documents"]
            handle = documents[0]["doc"]
            for name, code in sites():
                result = await session.call_tool("script_exec", {"doc": handle, "code": code})
                envelope = json.loads(result.content[0].text)
                shown = envelope.get("structured_content", {}).get(
                    "value_repr", envelope.get("detail")
                )
                print(f"{name} status={envelope['status']} value={shown} code={code[:70]}")


asyncio.run(main())
