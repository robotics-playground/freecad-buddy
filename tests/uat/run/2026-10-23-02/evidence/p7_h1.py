"""p0_h1.py for phase P7, plus two things TC-09 asks of the H1 host:
- a second ``tools/list`` after the last call (TC-09-15, TC-09-19: the host still answers);
- ``--snap <stem>``: after call n, copy the file named by FREECAD_BUDDY_AUDIT_LOG to
  ``evidence/<stem>_<n>.jsonl`` (TC-09-20 snapshots), and print its byte count.

    p7_h1.py <tag> [--snap <stem>] [NAME=VALUE ...] -- <tool> '<json>' [<tool> '<json>' ...]

Writes ``evidence/<tag>.jsonl`` (tools/list, every call and result, the closing tools/list) and
``evidence/<tag>.stderr.log`` (the host's stderr). Every call result keeps ``isError``.
"""

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from mcp_client import to_result  # noqa: E402
from scenario import substitute  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
H1_PYTHON = os.environ["FCB_PYTHON"]
FREECAD_BIN = r"C:\Program Files\FreeCAD 1.1\bin"


async def main():
    tag = sys.argv[1]
    split = sys.argv.index("--")
    head = sys.argv[2:split]
    snap = None
    if head[:1] == ["--snap"]:
        snap, head = head[1], head[2:]
    extra = dict(pair.split("=", 1) for pair in head)
    pairs = sys.argv[split + 1:]
    env = {k: v for k, v in os.environ.items() if not k.startswith("FREECAD_BUDDY_")}
    env["PYTHONPATH"] = FREECAD_BIN + os.pathsep + str(Path(FREECAD_BIN).parent / "lib")
    env["PATH"] = FREECAD_BIN + os.pathsep + env.get("PATH", "")
    env.update(extra)
    params = StdioServerParameters(
        command=H1_PYTHON,
        args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"],
        env=env,
        cwd=str(EVIDENCE),
    )
    log = (EVIDENCE / f"{tag}.jsonl").open("w", encoding="utf-8")
    with (EVIDENCE / f"{tag}.stderr.log").open("w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = sorted(t.name for t in (await session.list_tools()).tools)
                log.write(json.dumps({"tools_list": names, "count": len(names)}) + "\n")
                print(json.dumps({"tools_list_count": len(names), "script_exec": "script_exec" in names}))
                bindings = {}
                for number, (tool, raw) in enumerate(zip(pairs[::2], pairs[1::2]), 1):
                    args = substitute(json.loads(raw), bindings)
                    call_result = await session.call_tool(tool, args)
                    result = to_result(call_result)
                    bindings["PREV"] = bindings[f"R{number}"] = result
                    entry = {"mcp": tool, "args": args, "is_error": bool(call_result.isError),
                             "structured_content_is_null": call_result.structuredContent is None, "result": result}
                    log.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    log.flush()
                    print(json.dumps(entry, ensure_ascii=False)[:1500])
                    if snap:
                        source = Path(env["FREECAD_BUDDY_AUDIT_LOG"])
                        target = EVIDENCE / f"{snap}_{number}.jsonl"
                        shutil.copyfile(source, target)
                        print(f"snapshot {target.name}: {target.stat().st_size} bytes")
                names = sorted(t.name for t in (await session.list_tools()).tools)
                log.write(json.dumps({"tools_list_after": names, "count": len(names)}) + "\n")
                print(json.dumps({"tools_list_after_count": len(names)}))


if __name__ == "__main__":
    asyncio.run(main())
