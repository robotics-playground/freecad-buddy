"""TC-10-10 on H1: one overrunning mutation (debug_exec, 40 s busy then adds LateBox), no bridge retry."""
import asyncio
import json
import shutil
import subprocess
import time

from tc10lib import BOX, E, REPO, Log, h1

log = Log("tc-10-10.jsonl")
AUDIT = E / "tc-10-10-audit-full.jsonl"
CODE = ("import time\nt=time.time()\nwhile time.time()-t<40:\n    pass\n"
        "b=doc.addObject('Part::Box','LateBox')\nb.Length=5\nb.Width=5\nb.Height=5\n"
        "b.Placement.Base=FreeCAD.Vector(0,25,0)\ndoc.recompute()\nresult='late box added'\n")


def h1_pid():
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like "
          "'*freecad_buddy.hosts.main serve --transport stdio*' } | Sort-Object CreationDate | "
          "Select-Object -Last 1 -ExpandProperty ProcessId")
    return int(subprocess.run(["powershell", "-NoProfile", "-c", ps], capture_output=True, text=True).stdout.strip())


def cpu(pid):
    return float(subprocess.run(["powershell", "-NoProfile", "-c", f"(Get-Process -Id {pid}).TotalProcessorTime.TotalSeconds"],
                                capture_output=True, text=True).stdout.strip())


def find_fp(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "fingerprint_before" and isinstance(v, str):
                return v
            r = find_fp(v)
            if r:
                return r
    return None


async def wait_idle(pid, limit=40):
    t = time.time()
    while time.time() - t < limit:
        a = cpu(pid)
        await asyncio.sleep(1.0)
        if cpu(pid) - a < 0.2:
            return round(time.time() - t, 1)
    return f"still busy after {limit} s"


async def main():
    AUDIT.unlink(missing_ok=True)
    out = {}
    async with h1(log, "10", str(E / "tc-10-10-server.stderr.log"),
                  extra={"FREECAD_BUDDY_ALLOW_EXEC": "1", "FREECAD_BUDDY_AUDIT_LOG": str(AUDIT)}) as s:
        F = (await s.call("document_open", {"path": BOX}))["structured_content"]["doc"]
        pid = h1_pid()
        prev = lambda: s.call("preview_dry_run", {"doc": F, "operation": {"tool": "feature_body_create", "args": {"name": "Body"}}, "render": "off"})
        p0 = await prev()
        names0 = [n["name"] for n in (await s.call("query_tree_summary", {"doc": F}))["structured_content"]["tree"]]
        out["before"] = {"preview_status": p0.get("status"), "fingerprint": find_fp(p0), "objects": names0}
        t0 = time.time()
        m = await s.call("debug_exec", {"doc": F, "code": CODE})
        msg = (m.get("detail") or {}).get("message") or ""
        out["mutation"] = {"status": m.get("status"), "seconds": round(time.time() - t0, 2), "message": msg,
                           "no_blind_retry_text": "the document is now suspect: do not blind-retry, run a query_* read first to confirm " in msg}
        out["waited_idle_s"] = await wait_idle(pid)
        r = await s.call("query_tree_summary", {"doc": F})
        names1 = [n["name"] for n in r["structured_content"]["tree"]]
        p1 = await prev()
        out["after"] = {"clearing_read": r.get("status"), "objects": names1, "preview_status": p1.get("status"), "fingerprint": find_fp(p1)}
        out["landed"] = "LateBox" in names1
        out["digest_differs"] = out["before"]["fingerprint"] != out["after"]["fingerprint"]
        shutil.copy(AUDIT, E / "tc-10-10-audit.jsonl")
        recs = [json.loads(ln) for ln in open(AUDIT, encoding="utf-8")]
        ex = [a for a in recs if a.get("tool") == "debug_exec"]
        out["audit_debug_exec"] = [{"verdict": a.get("verify_verdict"), "digest": a["params_digest"][:16], "ts": a["ts"]} for a in ex]
        out["audit_counts_before_manual_retry"] = {
            "before_lines": sum(1 for a in ex if a.get("verify_verdict") is None),
            "after_lines": sum(1 for a in ex if a.get("verify_verdict") is not None),
            "distinct_digests": len({a["params_digest"] for a in ex})}
        sv = await s.call("document_save", {"doc": F, "path": str(E / "tc-10-10-F.FCStd")})
        out["save_for_gui_visual"] = sv.get("status")
        t1 = time.time()
        m2 = await s.call("debug_exec", {"doc": F, "code": CODE})
        out["manual_retry"] = {"status": m2.get("status"), "seconds": round(time.time() - t1, 2),
                               "terminal": m2.get("status") in {"OK", "TIMEOUT", "INVALID_INPUT", "RECOMPUTE_ERROR", "SPEC_FAILED", "WORKER_CRASHED"}}
        out["manual_retry"]["waited_idle_s"] = await wait_idle(pid)
        fit = await s.call("view_fit_viewport", {"doc": F})
        out["h1_view_fit_viewport"] = {"status": fit.get("status"), "message": (fit.get("detail") or {}).get("message")}
        await s.call("document_close", {"doc": F})
    g = subprocess.run(["grep", "-rniE", "retry|re-?issue", "src/freecad_buddy/adapters/mcp_server.py",
                        "src/freecad_buddy/adapters/rpc_listener.py"], cwd=str(REPO), capture_output=True, text=True)
    out["grep_retry"] = g.stdout.strip().splitlines()
    (E / "tc-10-10-checks.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


asyncio.run(main())
