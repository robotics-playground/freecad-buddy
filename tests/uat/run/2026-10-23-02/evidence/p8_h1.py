"""H1 (headless stdio host) driver for phase P8 (TC-10): one MCP stdio client session per run,
every call timed from tool-call entry to result return.

    p8_h1.py six        TC-10-01: open the golden box, six reads back to back -> tc-10-01-six-spans.json
    p8_h1.py latency    TC-10-02: read-only calls over the 5 golden models -> tc-10-02-latency.json
    p8_h1.py preview    TC-10-05: a ~100 s preview_dry_run, then document_list on the same session
    p8_h1.py chain      TC-10-07 .. TC-10-11 on one session; pauses at WAIT <name> until the file
                        $P8_GO_DIR/p8-go-<name> exists, so the agent can take the GUI captures

The host runs as in p0_h1.py / h1-setup.txt: the interpreter in FCB_PYTHON, PYTHONPATH and PATH to
FreeCAD 1.1.4, every inherited FREECAD_BUDDY_* removed, the scenario's audit log, cwd evidence.
Every call goes to evidence/<tag>-h1.jsonl (preview_id values cut to 16 characters) with its wall
start/end, seconds since the session start and duration; CHECK lines go to stdout and to
evidence/<tag>-h1-checks.txt.
"""

import asyncio
import json
import os
import re
import shutil
import statistics
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
MODELS = ["box-10-20-30", "cylinder-r5-h20", "sphere-r10", "box40-hole-r5", "two-box-compound"]
H1_PYTHON = os.environ["FCB_PYTHON"]
# One offset for the whole run: time.time() steps in 15.6 ms ticks on Windows, perf_counter does not.
EPOCH_OFFSET = time.time() - time.perf_counter()
FREECAD_BIN = r"C:\Program Files\FreeCAD 1.1\bin"
GO_DIR = Path(os.environ.get("P8_GO_DIR", str(EVIDENCE)))
TIMEOUTS = {"document_open": 60.0, "document_close": 30.0, "document_list": 30.0, "query_tree_summary": 30.0,
            "query_object": 30.0, "query_mass_properties": 30.0, "query_placement": 30.0,
            "query_dependencies": 30.0, "query_screenshot": 60.0, "verify_shape": 60.0,
            "verify_recompute": 120.0, "query_capabilities": 30.0}


def now():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def status_of(result):
    if "status" in result:
        return result["status"]
    first = (result.get("text") or "").splitlines()[0] if (result.get("text") or "").strip() else ""
    return first.split(":", 1)[0] if ":" in first else None


def message_of(result):
    if "status" in result:
        detail = result.get("detail")
        return detail.get("message") if isinstance(detail, dict) else None
    first = (result.get("text") or "").splitlines()[0] if (result.get("text") or "").strip() else ""
    return first.split(": ", 1)[1] if ": " in first else None


def data_of(result):
    detail = result.get("detail")
    return detail.get("data") if isinstance(detail, dict) else None


def redact(value):
    if isinstance(value, dict):
        return {k: (v[:16] + "...(redacted)" if k == "preview_id" and isinstance(v, str) else redact(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


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


async def h1_processes():
    text = await powershell("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "
                            "'*freecad_buddy.hosts*' } | Select-Object ProcessId,ParentProcessId,CommandLine "
                            "| ConvertTo-Json -Compress")
    rows = json.loads(text) if text else []
    return rows if isinstance(rows, list) else [rows]


async def worker_pid(session_out):
    """The worker that runs FreeCAD: the leaf of the processes whose command line ends
    ``-m freecad_buddy.hosts.headless.worker`` (a uv venv python.exe is a launcher that starts the
    base interpreter as its child, so the command line appears on two processes)."""
    rows = await h1_processes()
    workers = [r for r in rows if r["CommandLine"].rstrip().endswith("-m freecad_buddy.hosts.headless.worker")]
    parents = {r["ParentProcessId"] for r in rows}
    leaf = [r for r in workers if r["ProcessId"] not in parents]
    session_out.check("H1 process tree", [(r["ProcessId"], r["ParentProcessId"], r["CommandLine"][-60:]) for r in rows])
    return leaf[0]["ProcessId"] if len(leaf) == 1 else None


async def cpu(pid):
    started = time.perf_counter()
    text = await powershell(f"(Get-Process -Id {pid}).CPU")
    return {"at": now(), "t": started, "cpu": text}


class Session:
    def __init__(self, session, tag):
        self.session = session
        self.t0 = time.perf_counter()
        self.tag = tag
        self.calls = []
        self._open_logs(tag)

    def _open_logs(self, tag):
        self.tag = tag
        self.log = (EVIDENCE / f"{tag}-h1.jsonl").open("a", encoding="utf-8")
        self.checks = (EVIDENCE / f"{tag}-h1-checks.txt").open("a", encoding="utf-8")

    def switch(self, tag):
        self.log.close()
        self.checks.close()
        self._open_logs(tag)

    def check(self, label, value):
        line = f"CHECK {label}: {json.dumps(value, ensure_ascii=False, default=str)[:4000]}"
        print(line, flush=True)
        self.checks.write(f"{now()} {line}\n")
        self.checks.flush()

    async def call(self, tool, args, label=""):
        start = time.perf_counter()
        wall_start = EPOCH_OFFSET + start
        iso_start = now()
        raw = await self.session.call_tool(tool, args)
        end = time.perf_counter()
        result = to_result(raw)
        entry = {"label": label, "tool": tool, "args": args, "start": iso_start, "end": now(),
                 "epoch_start": wall_start, "epoch_end": wall_start + (end - start),
                 "t_start": round(start - self.t0, 3), "t_end": round(end - self.t0, 3),
                 "duration_s": round(end - start, 3), "is_error": bool(raw.isError),
                 "structured": raw.structuredContent is not None, "status": status_of(result),
                 "result": redact(result)}
        self.log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.log.flush()
        self.calls.append(entry)
        shown = {k: (v if len(str(v)) < 160 else str(v)[:160] + "...") for k, v in args.items() if k != "doc"}
        print(f"== [{label}] {tool} {json.dumps(shown, ensure_ascii=False)} t={entry['t_start']}..{entry['t_end']} "
              f"dur={entry['duration_s']} status={entry['status']} msg={str(message_of(result))[:300]}", flush=True)
        return entry

    async def pause(self, name):
        flag = GO_DIR / f"p8-go-{name}"
        print(f"WAIT {name} {now()}", flush=True)
        while not flag.exists():
            await asyncio.sleep(1)
        print(f"GO {name} {now()}", flush=True)


async def open_model(s, stem, label):
    opened = await s.call("document_open", {"path": str(GOLDEN / f"{stem}.FCStd")}, label)
    doc = ((opened["result"].get("structured_content") or {}).get("doc"))
    return doc


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
    overlaps = [i for i in range(1, len(spans)) if spans[i]["start"] < spans[i - 1]["end"]]
    s.check("spans overlapping the previous span", overlaps)
    s.check("statuses", [x["status"] for x in spans])
    s.check("tool order equals sent order", [x["tool"] for x in spans] == [t for t, _ in sent])
    await s.call("document_close", {"doc": doc}, "cleanup close")


async def scenario_latency(s):
    rows = []
    for stem in MODELS:
        opened = await s.call("document_open", {"path": str(GOLDEN / f"{stem}.FCStd")}, f"open {stem}")
        doc = (opened["result"].get("structured_content") or {}).get("doc")
        rows.append(opened)
        tree = await s.call("query_tree_summary", {"doc": doc}, stem)
        rows.append(tree)
        obj = tree_names(tree["result"])[0]
        for tool, args in (("query_object", {"doc": doc, "object": obj}),
                           ("query_mass_properties", {"doc": doc, "object": obj}),
                           ("query_placement", {"doc": doc, "object": obj}),
                           ("verify_shape", {"doc": doc, "object": obj}),
                           ("verify_recompute", {"doc": doc}),
                           ("query_screenshot", {"doc": doc, "view": {"camera": "iso"}}),
                           ("document_list", {})):
            rows.append(await s.call(tool, args, stem))
        rows.append(await s.call("document_close", {"doc": doc}, f"close {stem}"))
    latency = [{"tool": r["tool"], "duration_s": r["duration_s"], "status": r["status"]} for r in rows]
    (EVIDENCE / "tc-10-02-latency.json").write_text(json.dumps(latency, indent=1), encoding="utf-8")
    sampled = [r["duration_s"] for r in latency if r["tool"].startswith(("query_", "verify_", "document_list"))]
    s.check("sampled read-only calls / median", [len(sampled), statistics.median(sampled)])
    s.check("statuses not OK", [(r["tool"], r["status"]) for r in latency if r["status"] != "OK"])
    s.check("query_screenshot entries", [r for r in latency if r["tool"] == "query_screenshot"])
    s.check("calls at or over their tool_catalog timeout",
            [r for r in latency if r["duration_s"] >= TIMEOUTS.get(r["tool"], 0)])
    s.check("max duration per tool", {t: max(r["duration_s"] for r in latency if r["tool"] == t)
                                      for t in sorted({r["tool"] for r in latency})})


async def scenario_preview(s):
    created = await s.call("document_create", {"label": "TC1005Slow"}, "given create")
    doc = (created["result"].get("structured_content") or {}).get("doc")
    code = (f"import sys\nsys.path.insert(0, r'{EVIDENCE}')\nimport p8_slow\n"
            "p8_slow.Slow(doc.addObject('Part::FeaturePython', 'Slow'), 100)\nresult = 'slow object added, not recomputed'")
    await s.call("script_exec", {"doc": doc, "code": code}, "given slow object")
    await s.call("query_tree_summary", {"doc": doc}, "given tree")
    pid = await worker_pid(s)
    s.check("worker pid", pid)
    preview = await s.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_body_create",
                                                                          "args": {"name": "PreviewBody"}}}, "when preview")
    s.check("preview status / duration_s", [preview["status"], preview["duration_s"]])
    listed = await s.call("document_list", {}, "when document_list same session")
    documents = (listed["result"].get("structured_content") or {}).get("documents", [])
    s.check("document_list status", listed["status"])
    s.check("document_list entries", [(d.get("doc"), d.get("name"), d.get("label")) for d in documents])
    s.check("FCB_TMP_prev_ names in document_list",
            [d for d in documents if str(d.get("name") or "").startswith("FCB_TMP_prev_")
             or str(d.get("label") or "").startswith("FCB_TMP_prev_")])
    folders = sorted((EVIDENCE / "freecad-buddy-workdir" / "tmp").glob(f"FCB_TMP_session_{pid}_*"))
    s.check("session temp folders for the worker pid", [str(f) for f in folders])
    s.check("FCB_TMP_prev_* entries in them", [p.name for f in folders for p in f.iterdir()
                                               if p.name.startswith("FCB_TMP_prev_")])
    s.check("all entries in them", [p.name for f in folders for p in f.iterdir()])
    await s.call("document_close", {"doc": doc}, "cleanup close")


def audit_lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def wait_until(s, seconds_after, t0):
    delay = t0 + seconds_after - time.perf_counter()
    if delay > 0:
        await asyncio.sleep(delay)


async def wait_worker_idle(s, pid, not_before, t0, cap):
    """Poll the worker's CPU every 2 s from ``not_before`` s after t0 until it grows by < 0.1 s."""
    await wait_until(s, not_before, t0)
    previous = await cpu(pid)
    while time.perf_counter() - t0 < cap:
        await asyncio.sleep(2)
        current = await cpu(pid)
        s.check("worker CPU poll", [round(current["t"] - t0, 1), current["cpu"]])
        try:
            if float(current["cpu"]) - float(previous["cpu"]) < 0.1:
                return True
        except ValueError:
            return False
        previous = current
    return False


SLOW_75 = ("import time, Part\nend = time.monotonic() + 75\nwhile time.monotonic() < end:\n"
           "    Part.makeBox(10, 10, 10).fuse(Part.makeSphere(6))\nresult = 'done'")
LATE_40 = ("import time, Part\nend = time.monotonic() + 40\nwhile time.monotonic() < end:\n"
           "    Part.makeBox(10, 10, 10).fuse(Part.makeSphere(6))\nb = doc.addObject('Part::Box', 'LateBox'); "
           "b.Length = b.Width = b.Height = 5; b.Placement.Base.y = 25; doc.recompute()\nresult = 'done'")
SLOW_130 = ("import time, Part\nclass Slow:\n    def __init__(self, obj):\n        obj.Proxy = self\n"
            "    def execute(self, obj):\n        time.sleep(130)\n        obj.Shape = Part.makeBox(10, 10, 10)\n"
            "Slow(doc.addObject('Part::FeaturePython', 'Slow'))\nresult = 'built'")
ACCEPTED = "b = doc.addObject('Part::Box', 'AcceptedAfterRead'); b.Placement.Base.x = 15; result = 'ran'"


async def scenario_chain(s, names):
    audit = EVIDENCE / "tc-10-07-audit.jsonl"
    stderr = EVIDENCE / "tc-10-07-server.stderr.log"
    s.check("tools/list includes script_exec", "script_exec" in names)
    D = await open_model(s, "box-10-20-30", "given open D")
    E = await open_model(s, "cylinder-r5-h20", "given open E")
    e_tree = await s.call("query_tree_summary", {"doc": E}, "given tree E")
    e_obj = tree_names(e_tree["result"])[0]
    s.check("handles D E / E object", [D, E, e_obj])
    pid = await worker_pid(s)
    s.check("worker pid", pid)
    await s.pause("07")

    # TC-10-07
    t0 = time.perf_counter()
    first = await s.call("script_exec", {"doc": D, "code": SLOW_75}, "when 07 overrun")
    r = first["result"]
    s.check("07 envelope", r)
    s.check("07 elapsed_s", first["duration_s"])
    cpu1_task = asyncio.create_task(cpu(pid))
    await asyncio.sleep(0.2)
    q1 = await s.call("query_tree_summary", {"doc": E}, "when 07 tree E #1")
    s.check("07 q1 seconds after envelope / duration / text", [round(q1["t_start"] - first["t_end"], 3),
                                                              q1["duration_s"], q1["result"].get("text")])
    probe1 = await s.call("query_object", {"doc": E, "object": e_obj}, "informational probe (structured) 07 #1")
    s.check("07 informational structured probe #1 detail", probe1["result"].get("detail"))
    cpu1 = await cpu1_task
    await asyncio.sleep(max(0.0, cpu1["t"] + 3 - time.perf_counter()))
    cpu2 = await cpu(pid)
    s.check("07 worker CPU reads (s after t0, value)", [[round(cpu1["t"] - t0, 2), cpu1["cpu"]],
                                                        [round(cpu2["t"] - t0, 2), cpu2["cpu"]]])
    await wait_until(s, 65, t0)
    q2 = await s.call("query_tree_summary", {"doc": E}, "when 07 tree E #2 (~65 s)")
    s.check("07 q2 t / text", [round(q2["t_start"] - (t0 - s.t0), 2), q2["result"].get("text")])
    probe2 = await s.call("query_object", {"doc": E, "object": e_obj}, "informational probe (structured) 07 #2")
    s.check("07 informational structured probe #2 detail", probe2["result"].get("detail"))
    s.check("07 Get-Process worker after escalation", await powershell(f"Get-Process -Id {pid} | Select-Object Id,ProcessName,CPU | Format-List | Out-String"))
    await wait_until(s, 85, t0)
    q3 = await s.call("query_tree_summary", {"doc": E}, "when 07 tree E #3 (~85 s)")
    s.check("07 q3 t / text", [round(q3["t_start"] - (t0 - s.t0), 2), q3["result"].get("text")])
    s.check("07 audit lines with verify_verdict TIMEOUT",
            [(a.get("tool"), a.get("verify_verdict")) for a in audit_lines(audit) if a.get("verify_verdict") == "TIMEOUT"])
    await s.pause("08")

    # TC-10-08
    s.switch("tc-10-08")
    size_before = stderr.stat().st_size
    marker_d = EVIDENCE / "tc-10-08-D.marker"
    marker_e = EVIDENCE / "tc-10-08-E.marker"
    d_call = await s.call("script_exec", {"doc": D, "code": f"open(r'{marker_d}', 'w').write('x'); result = 'ran'"},
                          "when 08 mutation on D")
    s.check("08 D envelope", d_call["result"])
    s.check("08 D marker exists", marker_d.exists())
    with stderr.open("rb") as handle:
        handle.seek(size_before)
        s.check("08 stderr bytes gained during the D call", handle.read().decode("utf-8", "replace"))
    s.check("08 audit INVALID_INPUT lines", [(a.get("tool"), a.get("verify_verdict"), (a.get("doc") or {}).get("handle"))
                                            for a in audit_lines(audit) if a.get("verify_verdict") == "INVALID_INPUT"])
    e_call = await s.call("script_exec", {"doc": E, "code": f"open(r'{marker_e}', 'w').write('x'); result = 'ran'"},
                          "when 08 mutation on E")
    s.check("08 E status / marker exists", [e_call["status"], marker_e.exists()])
    s.switch("tc-10-09")
    given = await s.call("query_tree_summary", {"doc": E}, "given 09 tree E")
    s.check("09 given tree E text", given["result"].get("text"))
    await s.pause("09")

    # TC-10-09
    marker_9 = EVIDENCE / "tc-10-09-D.marker"
    c1 = await s.call("query_object", {"doc": D, "object": "NoSuchObject"}, "when 09 failing read")
    c2 = await s.call("script_exec", {"doc": D, "code": f"open(r'{marker_9}', 'w').write('x'); result = 'ran'"},
                      "when 09 mutation after failing read")
    c3 = await s.call("query_tree_summary", {"doc": D}, "when 09 passing read")
    c4 = await s.call("script_exec", {"doc": D, "code": "b = doc.addObject('Part::Box', 'QuarantineCleared'); "
                                      "b.Length = b.Width = b.Height = 5; b.Placement.Base.x = 15; doc.recompute(); "
                                      "result = 'ran'"}, "when 09 mutation after passing read")
    s.check("09 c1 status / message", [c1["status"], message_of(c1["result"])])
    s.check("09 c2 status / message / marker exists", [c2["status"], message_of(c2["result"]), marker_9.exists()])
    s.check("09 c3 status / text", [c3["status"], c3["result"].get("text")])
    s.check("09 c4 status / message", [c4["status"], message_of(c4["result"]), c4["result"].get("structured_content")])
    tree = await s.call("query_tree_summary", {"doc": D}, "then 09 tree D")
    s.check("09 D tree", tree["result"].get("text"))
    saved = await s.call("document_save", {"doc": D, "path": str(EVIDENCE / "tc-10-09-D.FCStd")}, "then 09 save D")
    s.check("09 save status", [saved["status"], message_of(saved["result"])])
    s.switch("tc-10-10")
    F = await open_model(s, "box-10-20-30", "given 10 open F")
    f_tree = await s.call("query_tree_summary", {"doc": F}, "given 10 tree F")
    s.check("10 F handle / tree", [F, f_tree["result"].get("text")])
    await s.pause("10")

    # TC-10-10
    probe = {"doc": F, "operation": {"tool": "feature_body_create", "args": {"name": "FpProbe"}}}

    def digest(entry):
        mutation = ((entry["result"].get("structured_content") or {}).get("fingerprint_before")
                    or ((entry["result"].get("structured_content") or {}).get("mutation") or {}).get("fingerprint_before"))
        return mutation.get("digest") if isinstance(mutation, dict) else mutation

    fp1 = await s.call("preview_dry_run", probe, "when 10 fingerprint before")
    s.check("10 preview #1 structured keys", sorted((fp1["result"].get("structured_content") or {}).keys()))
    s.check("10 fingerprint_before #1", digest(fp1))
    t0 = time.perf_counter()
    late = await s.call("script_exec", {"doc": F, "code": LATE_40}, "when 10 overrun")
    s.check("10 overrun envelope", late["result"])
    idle = await wait_worker_idle(s, pid, 41, t0, 70)
    s.check("10 worker idle", [idle, round(time.perf_counter() - t0, 1)])
    read = await s.call("query_tree_summary", {"doc": F}, "when 10 clearing read")
    s.check("10 clearing read text", read["result"].get("text"))
    s.check("10 LateBox occurrences in the tree", tree_names(read["result"]).count("LateBox"))
    fp2 = await s.call("preview_dry_run", probe, "when 10 fingerprint after")
    s.check("10 fingerprint_before #2", digest(fp2))
    s.check("10 digests differ", digest(fp1) != digest(fp2))
    saved = await s.call("document_save", {"doc": F, "path": str(EVIDENCE / "tc-10-10-F.FCStd")}, "then 10 save F")
    s.check("10 save status", saved["status"])
    shutil.copyfile(audit, EVIDENCE / "tc-10-10-audit-before-retry.jsonl")
    exec_f = [a for a in audit_lines(audit) if a.get("tool") == "script_exec" and (a.get("doc") or {}).get("handle") == F]
    s.check("10 script_exec audit lines on F before the manual retry",
            [("after" if "verify_verdict" in a else "before", a.get("params_digest")[:16], a.get("verify_verdict"))
             for a in exec_f])
    retry_t0 = time.perf_counter()
    retry = await s.call("script_exec", {"doc": F, "code": LATE_40}, "then 10 manual retry")
    s.check("10 manual retry envelope", retry["result"])
    idle = await wait_worker_idle(s, pid, 41, retry_t0, 70)
    s.check("10 worker idle after retry", [idle, round(time.perf_counter() - retry_t0, 1)])
    after_retry = await s.call("query_tree_summary", {"doc": F}, "then 10 read after the retry body")
    s.check("10 tree after retry", after_retry["result"].get("text"))
    await s.pause("10b")

    # TC-10-11
    s.switch("tc-10-11")
    created = await s.call("document_create", {"label": "TC1011Slow"}, "given 11 create H")
    H = (created["result"].get("structured_content") or {}).get("doc")
    built = await s.call("script_exec", {"doc": H, "code": SLOW_130}, "given 11 slow object")
    s.check("11 build status", [built["status"], built["duration_s"]])
    h_tree = await s.call("query_tree_summary", {"doc": H}, "given 11 tree H")
    s.check("11 given tree H", h_tree["result"].get("text"))
    await s.pause("11")
    t0 = time.perf_counter()
    v = await s.call("verify_recompute", {"doc": H}, "when 11 overrunning read")
    s.check("11 verify_recompute envelope / duration", [v["result"], v["duration_s"]])
    m1 = await s.call("script_exec", {"doc": H, "code": ACCEPTED}, "when 11 mutation at once")
    s.check("11 m1 envelope / s after the read returned", [m1["result"], round(m1["t_start"] - v["t_end"], 3)])
    await wait_until(s, 140, t0)
    m2 = await s.call("script_exec", {"doc": H, "code": ACCEPTED}, "when 11 mutation after the body (~140 s)")
    s.check("11 m2 envelope", m2["result"])
    final = await s.call("query_tree_summary", {"doc": H}, "then 11 tree H")
    s.check("11 tree H / AcceptedAfterRead count", [final["result"].get("text"),
                                                    tree_names(final["result"]).count("AcceptedAfterRead")])
    await s.call("document_close", {"doc": H}, "cleanup 11 close H")


SCENARIOS = {
    "six": ("tc-10-01", "tc-10-01-h1-audit.jsonl", "tc-10-01-h1.stderr.log", scenario_six),
    "latency": ("tc-10-02", "tc-10-02-h1-audit.jsonl", "tc-10-02-h1.stderr.log", scenario_latency),
    "preview": ("tc-10-05", "tc-10-05-audit.jsonl", "tc-10-05-server.stderr.log", scenario_preview),
    "chain": ("tc-10-07", "tc-10-07-audit.jsonl", "tc-10-07-server.stderr.log", scenario_chain),
}


async def main():
    tag, audit, stderr, run = SCENARIOS[sys.argv[1]]
    env = {k: v for k, v in os.environ.items() if not k.startswith("FREECAD_BUDDY_")}
    env["PYTHONPATH"] = FREECAD_BIN + os.pathsep + str(Path(FREECAD_BIN).parent / "lib")
    env["PATH"] = FREECAD_BIN + os.pathsep + env.get("PATH", "")
    env["FREECAD_BUDDY_AUDIT_LOG"] = str(EVIDENCE / audit)
    params = StdioServerParameters(
        command=H1_PYTHON,
        args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"],
        env=env, cwd=str(EVIDENCE))
    print(f"H1 START {now()} tag={tag} FREECAD_BUDDY_AUDIT_LOG={env['FREECAD_BUDDY_AUDIT_LOG']} stderr={stderr}", flush=True)
    with (EVIDENCE / stderr).open("w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = sorted(t.name for t in (await session.list_tools()).tools)
                s = Session(session, tag)
                s.check("tools/list count / script_exec listed", [len(names), "script_exec" in names])
                if run is scenario_chain:
                    await run(s, names)
                else:
                    await run(s)
    print(f"H1 END {now()} (client stdin closed, host exited)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
