"""Drive the H1 headless host (serve --transport stdio --mode inline) through an MCP stdio client,
for phase R2 (from r0_h1.py and 2026-10-23-02 p7_h1.py).

    r2_h1.py <tag> [NAME=VALUE ...] -- <tool> '<json>' [<tool> '<json>' ...]

The H1 interpreter is ``$FCB_ENV/python.exe`` (``scratchpad/rerun/h1-env.txt``); PYTHONPATH and PATH
point at ``$FCB_ENV/Library/bin`` and ``Library/lib`` (APPENDIX-B step 3). Every inherited
FREECAD_BUDDY_* is removed, then the NAME=VALUE pairs are set. Set FREECAD_USER_HOME to a temp dir
before running. The host's stderr goes to ``evidence/<tag>-h1.stderr.log``; ``tools/list``, every
call (with ``isError`` and whether ``structuredContent`` is null) and a closing ``tools/list`` go to
``evidence/<tag>-h1.jsonl``. ``preview_id`` values are cut to 16 characters in the log; the full
value stays in memory for ``$PREV.<path>`` / ``$R<n>.<path>`` substitution.
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
FCB_ENV = Path(os.environ["FCB_ENV"])
H1_PYTHON = str(FCB_ENV / "python.exe")
FREECAD_BIN = str(FCB_ENV / "Library" / "bin")


def redact(value):
    if isinstance(value, dict):
        return {k: (v[:16] + "...(redacted)" if k == "preview_id" and isinstance(v, str) else redact(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


async def main():
    tag = sys.argv[1]
    split = sys.argv.index("--")
    extra = dict(pair.split("=", 1) for pair in sys.argv[2:split])
    pairs = sys.argv[split + 1:]
    env = {k: v for k, v in os.environ.items() if not k.startswith("FREECAD_BUDDY_")}
    env["PYTHONPATH"] = FREECAD_BIN + os.pathsep + str(FCB_ENV / "Library" / "lib")
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
                log.write(json.dumps({"env": {k: v for k, v in extra.items()}, "tools_list": names,
                                      "count": len(names)}) + "\n")
                print(json.dumps({"count": len(names), "script_exec": "script_exec" in names}))
                bindings = {}
                for number, (tool, raw) in enumerate(zip(pairs[::2], pairs[1::2]), 1):
                    args = substitute(json.loads(raw), bindings)
                    call_result = await session.call_tool(tool, args)
                    result = to_result(call_result)
                    bindings["PREV"] = bindings[f"R{number}"] = result
                    entry = {"mcp": tool, "args": redact(args), "is_error": bool(call_result.isError),
                             "structured_content_is_null": call_result.structuredContent is None,
                             "result": redact(result)}
                    log.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    log.flush()
                    print(json.dumps(entry, ensure_ascii=False)[:1500])
                names = sorted(t.name for t in (await session.list_tools()).tools)
                log.write(json.dumps({"tools_list_after": names, "count": len(names)}) + "\n")
                print(json.dumps({"tools_list_after_count": len(names)}))


if __name__ == "__main__":
    asyncio.run(main())
