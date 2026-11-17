"""p7_h1.py for phase P9 (TC-11), plus:
- ``@sh '<bash command>'`` as a pair runs the command (cwd evidence) between two calls and logs its output;
- every result is logged with ``preview_id`` cut to 16 characters;
- P9_SURFACE=<file>: write the whole tools/list (name, inputSchema as ``input_schema``, annotations) to evidence/<file>;
- one ``P9 H1`` line is appended to launch-log.tsv (start, end, the variables, the note in P9_NOTE).

    p9_h1.py <tag> [NAME=VALUE ...] -- <tool> '<json>' [<tool> '<json>' ...]

Writes ``evidence/<tag>.jsonl`` and ``evidence/<tag>.stderr.log`` (the host's stderr).
``$PREV.<path>`` reads the previous call result, ``$R<n>.<path>`` the n-th pair's result.
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from mcp_client import to_result  # noqa: E402
from scenario import substitute  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
H1_PYTHON = os.environ["FCB_PYTHON"]
FREECAD_BIN = r"C:\Program Files\FreeCAD 1.1\bin"
# Git Bash, not the WSL bash.exe that the Windows PATH lists first.
GIT_BASH = r"C:\Program Files\Git\usr\bin\bash.exe"


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
    env["PYTHONPATH"] = FREECAD_BIN + os.pathsep + str(Path(FREECAD_BIN).parent / "lib")
    env["PATH"] = FREECAD_BIN + os.pathsep + env.get("PATH", "")
    env.update(extra)
    params = StdioServerParameters(
        command=H1_PYTHON,
        args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"],
        env=env,
        cwd=str(EVIDENCE),
    )
    start = datetime.now().astimezone().isoformat(timespec="seconds")
    log = (EVIDENCE / f"{tag}.jsonl").open("w", encoding="utf-8")
    try:
        with (EVIDENCE / f"{tag}.stderr.log").open("w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    names = sorted(t.name for t in tools)
                    if os.environ.get("P9_SURFACE"):
                        surface = [{"name": t.name, "input_schema": t.inputSchema,
                                    "annotations": t.annotations.model_dump() if t.annotations else None}
                                   for t in tools]
                        (EVIDENCE / os.environ["P9_SURFACE"]).write_text(json.dumps(surface, indent=1),
                                                                          encoding="utf-8")
                    log.write(json.dumps({"tools_list": names, "count": len(names)}) + "\n")
                    print(json.dumps({"tools_list_count": len(names), "script_exec": "script_exec" in names}))
                    bindings = {}
                    for number, (tool, raw) in enumerate(zip(pairs[::2], pairs[1::2]), 1):
                        if tool == "@sh":
                            out = subprocess.run([GIT_BASH, "-c", raw], cwd=EVIDENCE, capture_output=True, text=True)
                            entry = {"sh": raw, "exit": out.returncode, "stdout": out.stdout, "stderr": out.stderr}
                            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
                            log.flush()
                            print(json.dumps(entry, ensure_ascii=False)[:1500])
                            continue
                        args = substitute(json.loads(raw), bindings)
                        call_result = await session.call_tool(tool, args)
                        result = to_result(call_result)
                        bindings["PREV"] = bindings[f"R{number}"] = result
                        entry = {"n": number, "mcp": tool, "args": redact(args), "is_error": bool(call_result.isError),
                                 "result": redact(result)}
                        log.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        log.flush()
                        print(json.dumps(entry, ensure_ascii=False)[:2500])
    finally:
        end = datetime.now().astimezone().isoformat(timespec="seconds")
        variables = " ".join(f"{k}={v}" for k, v in extra.items()) or "(no FREECAD_BUDDY_* set)"
        note = os.environ.get("P9_NOTE", tag)
        line = (f"P9 H1\t{start}\tH1 worker; host = stdio child of p9_h1.py (pid not recorded)\t"
                f"H1 venv scratchpad\\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence\t"
                f"{variables} (all other FREECAD_BUDDY_* removed) [{note}]\t{end}\n")
        with (EVIDENCE / "launch-log.tsv").open("a", encoding="utf-8") as handle:
            handle.write(line)


if __name__ == "__main__":
    asyncio.run(main())
