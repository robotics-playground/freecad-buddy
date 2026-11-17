"""TC-10-12 (phase P8): a long-running call through the :8765 proxy, FreeCAD ended mid-call.

    p8_kill.py <freecad pid> <doc>

Issues script_exec (a 25 s sleep, inside its 30 s budget) on <doc>; 5 s later ends the FreeCAD
process with Stop-Process -Force from this shell (same integrity level); reads what the in-flight
call returns under a hard 180 s deadline. Then, within 5 s of that envelope, reads the :8765
LISTENING rows and sends a tools/list to :8765. Everything goes to evidence/tc-10-12-kill.jsonl.
"""

import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVIDENCE = Path(__file__).resolve().parent
LOG = (EVIDENCE / "tc-10-12-kill.jsonl").open("a", encoding="utf-8")


def now():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def write(entry):
    entry = {"at": now(), **entry}
    LOG.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    LOG.flush()
    print(json.dumps(entry, ensure_ascii=False, default=str)[:2000], flush=True)


async def in_flight(doc):
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write_stream, _):
        async with ClientSession(read, write_stream) as session:
            await session.initialize()
            write({"step": "call sent", "tool": "script_exec"})
            result = await session.call_tool("script_exec", {"doc": doc, "code": "import time\ntime.sleep(25)\nresult = 'slept'"})
            return result


async def kill_later(pid):
    await asyncio.sleep(5)
    completed = subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force; 'stopped'"],
                               capture_output=True, text=True)
    write({"step": "Stop-Process -Force", "pid": pid, "output": (completed.stdout + completed.stderr).strip()})


async def tools_list():
    try:
        async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write_stream, _):
            async with ClientSession(read, write_stream) as session:
                await asyncio.wait_for(session.initialize(), 10)
                tools = await asyncio.wait_for(session.list_tools(), 10)
                return f"answered: {len(tools.tools)} tools"
    except BaseException as exc:  # noqa: BLE001 - the error type is the observation
        return f"error: {type(exc).__name__}: {exc!r}"[:600]


async def main():
    pid, doc = int(sys.argv[1]), sys.argv[2]
    started = time.monotonic()
    killer = asyncio.create_task(kill_later(pid))
    try:
        result = await asyncio.wait_for(in_flight(doc), 180)
        elapsed = round(time.monotonic() - started, 3)
        envelope = result.structuredContent
        write({"step": "in-flight call returned", "elapsed_s": elapsed, "isError": result.isError,
               "structuredContent": envelope, "text": [b.text for b in result.content if b.type == "text"]})
    except asyncio.TimeoutError:
        write({"step": "in-flight call hit the 180 s deadline", "elapsed_s": round(time.monotonic() - started, 3)})
    except BaseException as exc:  # noqa: BLE001
        write({"step": "in-flight call raised", "elapsed_s": round(time.monotonic() - started, 3), "error": repr(exc)[:800]})
    returned = time.monotonic()
    await killer
    rows = subprocess.run(["powershell", "-NoProfile", "-Command", "netstat -ano | Select-String ':8765\\s'"],
                          capture_output=True, text=True).stdout.strip()
    write({"step": ":8765 rows", "s_after_envelope": round(time.monotonic() - returned, 2), "rows": rows})
    deadline = returned + 5
    while rows and "LISTENING" in rows and time.monotonic() < deadline:
        await asyncio.sleep(0.5)
        rows = subprocess.run(["powershell", "-NoProfile", "-Command", "netstat -ano | Select-String ':8765\\s'"],
                              capture_output=True, text=True).stdout.strip()
        write({"step": ":8765 rows (poll)", "s_after_envelope": round(time.monotonic() - returned, 2), "rows": rows})
    write({"step": "tools/list against :8765", "s_after_envelope": round(time.monotonic() - returned, 2),
           "outcome": await tools_list()})
    write({"step": "client exits", "exit_code": 0})


if __name__ == "__main__":
    asyncio.run(main())
