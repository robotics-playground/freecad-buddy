"""H1 (headless stdio host) driver for phase R2, TC-10 (from 2026-10-23-02 p8_h1.py, trimmed): one MCP
stdio client session per run, every call timed from tool-call entry to result return.

    r2_h1chain.py six   TC-10-01: open the golden box, six reads back to back -> tc-10-01-six-spans.json
    r2_h1chain.py c07   TC-10-07: open D (box) and E (cylinder), pause at WAIT 07 until the file
                        $R2_GO_DIR/r2-go-07 exists (GUI captures), then the 75 s script_exec overrun and
                        the three query_object probes on E at about +0 s, +65 s and +85 s

The host runs from ``$FCB_ENV`` (scratchpad/rerun/h1-env.txt) with PYTHONPATH and PATH to
``$FCB_ENV/Library``, every inherited FREECAD_BUDDY_* removed, the scenario's audit log, cwd evidence.
Set FREECAD_USER_HOME to a temp dir first. Every call goes to evidence/<tag>-h1.jsonl with its wall
start/end and duration; CHECK lines go to stdout and evidence/<tag>-h1-checks.txt.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from mcp_client import to_result  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
REPO = EVIDENCE.parents[4]
GOLDEN = REPO / "benchmarks" / "g0" / "golden-models"
FCB_ENV = Path(os.environ["FCB_ENV"])
# One offset for the whole run: time.time() steps in 15.6 ms ticks on Windows, perf_counter does not.
EPOCH_OFFSET = time.time() - time.perf_counter()
GO_DIR = Path(os.environ.get("R2_GO_DIR", str(EVIDENCE)))
SLOW_75 = ("import time, Part\nend = time.monotonic() + 75\nwhile time.monotonic() < end:\n"
           "    Part.makeBox(10, 10, 10).fuse(Part.makeSphere(6))\nresult = 'done'")


def now():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def status_of(result):
    if "status" in result:
        return result["status"]
    first = (result.get("text") or "").splitlines()[0] if (result.get("text") or "").strip() else ""
    return first.split(":", 1)[0] if ":" in first else None


def tree_names(result):
    lines = (result.get("text") or "").splitlines()[1:]
    if lines and lines[0].startswith("framing:"):
        lines = lines[1:]
    return [line.split(" ")[2] for line in lines if line[:1] in ("v", "-") and len(line.split(" ")) > 2]


async def powershell(command):
    process = await asyncio.create_subprocess_exec("powershell", "-NoProfile", "-Command", command,
                                                   stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await process.communicate()
    return (out.decode(errors="replace") + err.decode(errors="replace")).strip()


async def worker_pid(s):
    """The leaf process whose command line ends ``-m freecad_buddy.hosts.headless.worker`` (a venv
    python.exe is a launcher that starts the base interpreter as its child)."""
    text = await powershell("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "
                            "'*freecad_buddy.hosts*' } | Select-Object ProcessId,ParentProcessId,CommandLine "
                            "| ConvertTo-Json -Compress")
    rows = json.loads(text) if text else []
    rows = rows if isinstance(rows, list) else [rows]
    workers = [r for r in rows if r["CommandLine"].rstrip().endswith("-m freecad_buddy.hosts.headless.worker")]
    parents = {r["ParentProcessId"] for r in rows}
    leaf = [r for r in workers if r["ProcessId"] not in parents]
    s.check("H1 process tree", [(r["ProcessId"], r["ParentProcessId"], r["CommandLine"][-60:]) for r in rows])
    return leaf[0]["ProcessId"] if len(leaf) == 1 else None


async def cpu(pid):
    started = time.perf_counter()
    return {"at": now(), "t": started, "cpu": await powershell(f"(Get-Process -Id {pid}).CPU")}


class Session:
    def __init__(self, session, tag):
        self.session = session
        self.t0 = time.perf_counter()
        self.log = (EVIDENCE / f"{tag}-h1.jsonl").open("a", encoding="utf-8")
        self.checks = (EVIDENCE / f"{tag}-h1-checks.txt").open("a", encoding="utf-8")

    def check(self, label, value):
        line = f"CHECK {label}: {json.dumps(value, ensure_ascii=False, default=str)[:4000]}"
        print(line, flush=True)
        self.checks.write(f"{now()} {line}\n")
        self.checks.flush()

    async def call(self, tool, args, label=""):
        start = time.perf_counter()
        iso_start = now()
        raw = await self.session.call_tool(tool, args)
        end = time.perf_counter()
        result = to_result(raw)
        entry = {"label": label, "tool": tool, "args": args, "start": iso_start, "end": now(),
                 "epoch_start": EPOCH_OFFSET + start, "epoch_end": EPOCH_OFFSET + end,
                 "t_start": round(start - self.t0, 3), "t_end": round(end - self.t0, 3),
                 "duration_s": round(end - start, 3), "is_error": bool(raw.isError),
                 "structured": raw.structuredContent is not None, "status": status_of(result), "result": result}
        self.log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.log.flush()
        print(f"== [{label}] {tool} t={entry['t_start']}..{entry['t_end']} dur={entry['duration_s']} "
              f"status={entry['status']}", flush=True)
        return entry

    async def pause(self, name):
        flag = GO_DIR / f"r2-go-{name}"
        print(f"WAIT {name} {now()}", flush=True)
        while not flag.exists():
            await asyncio.sleep(1)
        print(f"GO {name} {now()}", flush=True)


async def open_model(s, stem, label):
    opened = await s.call("document_open", {"path": str(GOLDEN / f"{stem}.FCStd")}, label)
    return (opened["result"].get("structured_content") or {}).get("doc")


async def scenario_six(s):
    doc = await open_model(s, "box-10-20-30", "given open")
    tree = await s.call("query_tree_summary", {"doc": doc}, "given tree")
    obj = tree_names(tree["result"])[0]
    sent = [("query_tree_summary", {"doc": doc}), ("query_object", {"doc": doc, "object": obj}),
            ("query_mass_properties", {"doc": doc, "object": obj}), ("query_placement", {"doc": doc, "object": obj}),
            ("verify_shape", {"doc": doc, "object": obj}), ("document_list", {})]
    spans = []
    for tool, args in sent:
        entry = await s.call(tool, args, "when six reads")
        spans.append({"tool": tool, "start": entry["epoch_start"], "end": entry["epoch_end"], "status": entry["status"]})
    (EVIDENCE / "tc-10-01-six-spans.json").write_text(json.dumps(spans, indent=1), encoding="utf-8")
    s.check("spans overlapping the previous span", [i for i in range(1, len(spans)) if spans[i]["start"] < spans[i - 1]["end"]])
    s.check("statuses", [x["status"] for x in spans])
    s.check("tool order equals sent order", [x["tool"] for x in spans] == [t for t, _ in sent])
    await s.call("document_close", {"doc": doc}, "cleanup close")


async def scenario_c07(s):
    audit = Path(os.environ["R2_AUDIT"])
    D = await open_model(s, "box-10-20-30", "given open D")
    E = await open_model(s, "cylinder-r5-h20", "given open E")
    e_obj = tree_names((await s.call("query_tree_summary", {"doc": E}, "given tree E"))["result"])[0]
    s.check("handles D E / E object", [D, E, e_obj])
    pid = await worker_pid(s)
    s.check("worker pid", pid)
    await s.pause("07")
    t0 = time.perf_counter()
    first = await s.call("script_exec", {"doc": D, "code": SLOW_75}, "when 07 overrun")
    s.check("07 envelope", first["result"])
    s.check("07 elapsed_s", first["duration_s"])
    cpu1 = await cpu(pid)
    q1 = await s.call("query_object", {"doc": E, "object": e_obj}, "when 07 query_object E #1")
    s.check("07 q1 s after envelope / duration / status / detail",
            [round(q1["t_start"] - first["t_end"], 3), q1["duration_s"], q1["status"], q1["result"].get("detail")])
    await asyncio.sleep(max(0.0, cpu1["t"] + 3 - time.perf_counter()))
    cpu2 = await cpu(pid)
    s.check("07 worker CPU reads (s after t0, value)", [[round(cpu1["t"] - t0, 2), cpu1["cpu"]],
                                                        [round(cpu2["t"] - t0, 2), cpu2["cpu"]]])
    await asyncio.sleep(max(0.0, t0 + 65 - time.perf_counter()))
    q2 = await s.call("query_object", {"doc": E, "object": e_obj}, "when 07 query_object E #2 (~65 s)")
    s.check("07 q2 s after t0 / status / detail", [round(q2["t_start"] - (t0 - s.t0), 2), q2["status"],
                                                   q2["result"].get("detail")])
    s.check("07 Get-Process worker after escalation",
            await powershell(f"Get-Process -Id {pid} | Select-Object Id,ProcessName,CPU | Format-List | Out-String"))
    await asyncio.sleep(max(0.0, t0 + 85 - time.perf_counter()))
    q3 = await s.call("query_object", {"doc": E, "object": e_obj}, "when 07 query_object E #3 (~85 s)")
    s.check("07 q3 s after t0 / status / detail", [round(q3["t_start"] - (t0 - s.t0), 2), q3["status"],
                                                   q3["result"].get("detail")])
    lines = [json.loads(x) for x in audit.read_text(encoding="utf-8").splitlines() if x.strip()] if audit.exists() else []
    s.check("07 audit lines with verify_verdict TIMEOUT",
            [(a.get("tool"), a.get("verify_verdict")) for a in lines if a.get("verify_verdict") == "TIMEOUT"])
    await s.pause("07end")


SCENARIOS = {
    "six": ("tc-10-01", "tc-10-01-h1-audit.jsonl", "tc-10-01-h1.stderr.log", scenario_six),
    "c07": ("tc-10-07", "tc-10-07-audit.jsonl", "tc-10-07-server.stderr.log", scenario_c07),
}


async def main():
    tag, audit, stderr, run = SCENARIOS[sys.argv[1]]
    env = {k: v for k, v in os.environ.items() if not k.startswith("FREECAD_BUDDY_")}
    env["PYTHONPATH"] = str(FCB_ENV / "Library" / "bin") + os.pathsep + str(FCB_ENV / "Library" / "lib")
    env["PATH"] = str(FCB_ENV / "Library" / "bin") + os.pathsep + env.get("PATH", "")
    env["FREECAD_BUDDY_AUDIT_LOG"] = str(EVIDENCE / audit)
    os.environ["R2_AUDIT"] = env["FREECAD_BUDDY_AUDIT_LOG"]
    params = StdioServerParameters(command=str(FCB_ENV / "python.exe"),
                                   args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio",
                                         "--mode", "inline"], env=env, cwd=str(EVIDENCE))
    print(f"H1 START {now()} tag={tag} FREECAD_BUDDY_AUDIT_LOG={env['FREECAD_BUDDY_AUDIT_LOG']} stderr={stderr}", flush=True)
    with (EVIDENCE / stderr).open("w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = sorted(t.name for t in (await session.list_tools()).tools)
                s = Session(session, tag)
                s.check("tools/list count / script_exec listed", [len(names), "script_exec" in names])
                await run(s)
    print(f"H1 END {now()} (client stdin closed, host exited)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
