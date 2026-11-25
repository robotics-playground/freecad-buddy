"""Fit the open document and save a screenshot of the container FreeCAD window."""

import asyncio
import json
import subprocess
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

SHOT = "/tmp/verify-13-8.png"


def cua(tool, arguments):
    out = subprocess.run(
        ["docker", "exec", "-u", "cua", "fcb-desktop", "bash", "-c",
         'eval "$(fcb-session-env)"; exec /usr/local/bin/cua-driver call "$1" "$2"',
         "cua-driver", tool, json.dumps(arguments)],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out[out.find("{"):])


async def main():
    async with streamable_http_client("http://127.0.0.1:18765/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            docs = (await session.call_tool("document_list", {})).structuredContent
            doc = docs["structured_content"]["documents"][-1]["doc"]
            print((await session.call_tool("view_fit_viewport", {"doc": doc})).structuredContent.get("status"))
    window = next(w for w in cua("list_windows", {})["windows"] if w["app_name"] == "FreeCAD")
    subprocess.run(["docker", "exec", "-u", "cua", "fcb-desktop", "rm", "-f", SHOT], check=True)
    cua("get_window_state", {"pid": window["pid"], "window_id": window["window_id"],
                             "include_accessibility_tree": False, "screenshot_out_file": SHOT})
    subprocess.run(["docker", "cp", f"fcb-desktop:{SHOT}", sys.argv[1]], check=True)
    print("saved", sys.argv[1])


asyncio.run(main())
