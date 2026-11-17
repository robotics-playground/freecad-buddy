"""Drive the H1 headless host (serve --transport stdio --mode inline) through an MCP stdio client.

    p0_h1.py <tag> [NAME=VALUE ...] -- <tool> '<json>' [<tool> '<json>' ...]

The H1 interpreter is a venv on FreeCAD 1.1.4's own Python 3.11 with ``mcp`` and the repo package
installed (the ``fcb`` micromamba env named by the test plan is not on this machine). ``import
FreeCAD`` resolves through PYTHONPATH to the FreeCAD bin folder, as in APPENDIX-B step 3. The
host's stderr goes to ``evidence/<tag>-h1.stderr.log``; ``tools/list`` names and every call result
go to ``evidence/<tag>-h1.jsonl``. ``$PREV.<path>`` in an argument reads the previous result, ``$R<n>.<path>`` the n-th.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from mcp_client import to_result  # noqa: E402
from scenario import substitute  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
H1_PYTHON = os.environ.get("FCB_PYTHON", str(Path(os.environ["TEMP"]) / "claude" / "h1env" / "Scripts" / "python.exe"))
FREECAD_BIN = r"C:\Program Files\FreeCAD 1.1\bin"


async def main():
    tag = sys.argv[1]
    split = sys.argv.index("--")
    extra = dict(pair.split("=", 1) for pair in sys.argv[2:split])
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
    log = (EVIDENCE / f"{tag}-h1.jsonl").open("w", encoding="utf-8")
    with (EVIDENCE / f"{tag}-h1.stderr.log").open("w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = sorted(t.name for t in (await session.list_tools()).tools)
                log.write(json.dumps({"tools_list": names, "count": len(names)}) + "\n")
                print(json.dumps({"count": len(names), "script_exec": "script_exec" in names}))
                bindings = {}
                for number, (tool, raw) in enumerate(zip(pairs[::2], pairs[1::2]), 1):
                    args = substitute(json.loads(raw), bindings)
                    result = to_result(await session.call_tool(tool, args))
                    bindings["PREV"] = bindings[f"R{number}"] = result
                    entry = {"mcp": tool, "args": args, "result": result}
                    log.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    print(json.dumps(entry, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    asyncio.run(main())
