"""TC-10-07, -08, -09 on ONE H1 session (the document-suspect set lives in that server's memory).
On H1 the only call whose budget is enforced is debug_exec (30 s, ThreadExecutor); every other tool
runs on InlineExecutor and cannot time out (adapters/marshal.py:57-62, hosts/tool_catalog.py:1427-1468).
So the overrunning mutation is debug_exec with a bounded 45 s CPU-busy body. GUI captures run between
the steps through gui.py; the GUI shows the golden box opened through the listener before this runs."""
import asyncio
import json
import shutil
import subprocess
import time

from tc10lib import BOX, CYL, E, REPO, Log, gui_py, h1

log = Log("tc-10-0709.jsonl")
AUDIT = E / "tc-10-0709-audit.jsonl"
ERR = E / "tc-10-0709-server.stderr.log"
out = {}
BUSY = "import time\nt=time.time()\nwhile time.time()-t<45:\n    pass\nresult='busy body finished'\n"


def marker(name):
    p = (E / f"tc-10-{name}.marker").as_posix()
    return p, f"open({p!r},'w').write('dispatched')\nresult='marker written'\n"


def h1_pid():
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like "
          "'*freecad_buddy.hosts.main serve --transport stdio*' } | Sort-Object CreationDate | "
          "Select-Object -Last 1 -ExpandProperty ProcessId")
    return int(subprocess.run(["powershell", "-NoProfile", "-c", ps], capture_output=True, text=True).stdout.strip())


def cpu_seconds(pid):
    r = subprocess.run(["powershell", "-NoProfile", "-c", f"(Get-Process -Id {pid}).TotalProcessorTime.TotalSeconds"],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def msg(env):
    return (env.get("detail") or {}).get("message") or ""


async def main():
    for n in ("08-D", "08-E", "09-a", "09-b"):
        (E / f"tc-10-{n}.marker").unlink(missing_ok=True)
    async with h1(log, "0709", str(ERR), extra={"FREECAD_BUDDY_ALLOW_EXEC": "1",
                                               "FREECAD_BUDDY_AUDIT_LOG": str(AUDIT)}) as s:
        D = (await s.call("document_open", {"path": BOX}))["structured_content"]["doc"]
        Ed = (await s.call("document_open", {"path": CYL}))["structured_content"]["doc"]
        pid = h1_pid()
        out["handles"] = {"D": D, "E": Ed, "h1_pid": pid}

        # ---------------- TC-10-07
        t0 = time.time()
        env = await s.call("debug_exec", {"doc": D, "code": BUSY})
        t1 = time.time()
        c0 = cpu_seconds(pid)
        await asyncio.sleep(3)
        c1 = cpu_seconds(pid)
        data = (env.get("detail") or {}).get("data") or {}
        out["07"] = {"seconds": round(t1 - t0, 2), "status": env.get("status"),
                     "marshal_timeout": data.get("marshal_timeout"), "maybe_still_running": data.get("maybe_still_running"),
                     "message": msg(env),
                     "has_consequence": "the document is now suspect: do not blind-retry, run a query_* read first to confirm " in msg(env),
                     "cpu_s_in_3s_after_envelope": round(c1 - c0, 2)}
        t2 = time.time()
        dl = await s.call("document_list", {})
        out["07"]["followup_document_list"] = {"status": dl.get("status"), "seconds": round(time.time() - t2, 2),
                                               "returned_at_s_after_debug_exec_start": round(time.time() - t0, 2)}
        shutil.copy(AUDIT, E / "tc-10-07-audit.jsonl")
        out["07"]["audit_timeout_lines"] = sum('"verify_verdict": "TIMEOUT"' in ln for ln in open(AUDIT, encoding="utf-8"))
        out["07"]["after_shot"] = gui_py("shot", "tc-10-07-after.png")

        # ---------------- TC-10-08
        out["08"] = {"before_shot": gui_py("shot", "tc-10-08-before.png")}
        err_n = len(open(ERR, encoding="utf-8").readlines())
        pD, codeD = marker("08-D")
        envD = await s.call("debug_exec", {"doc": D, "code": codeD})
        pE, codeE = marker("08-E")
        envE = await s.call("debug_exec", {"doc": Ed, "code": codeE})
        shutil.copy(AUDIT, E / "tc-10-08-audit.jsonl")
        audit = [json.loads(ln) for ln in open(AUDIT, encoding="utf-8")]
        out["08"].update({
            "D_status": envD.get("status"), "D_message": msg(envD),
            "D_startswith": msg(envD).startswith("document-suspect: a prior call timed out on this document and its body may "),
            "D_contains_operator_hint": "run a query_* read to confirm the document still responds " in msg(envD),
            "D_marker_exists": (E / "tc-10-08-D.marker").exists(),
            "stderr_new_lines_during_D": open(ERR, encoding="utf-8").readlines()[err_n:],
            "audit_invalid_input_lines": [a for a in audit if a.get("verify_verdict") == "INVALID_INPUT"],
            "E_status": envE.get("status"), "E_message": msg(envE), "E_marker_exists": (E / "tc-10-08-E.marker").exists(),
        })
        out["08"]["after_shot"] = gui_py("shot", "tc-10-08-after.png")

        # ---------------- TC-10-09
        out["09"] = {"before_shot": gui_py("shot", "tc-10-09-before.png")}
        r1 = await s.call("query_object", {"doc": D, "object": "NoSuchObject"})
        _, codeA = marker("09-a")
        r2 = await s.call("debug_exec", {"doc": D, "code": codeA})
        r3 = await s.call("query_tree_summary", {"doc": D})
        codeB = (marker("09-b")[1] + "b=doc.addObject('Part::Box','QuarantineCleared')\nb.Length=5\nb.Width=5\nb.Height=5\n"
                 "b.Placement.Base=FreeCAD.Vector(15,0,0)\ndoc.recompute()\n")
        r4 = await s.call("debug_exec", {"doc": D, "code": codeB})
        out["09"].update({
            "1_failing_read": {"status": r1.get("status"), "message": msg(r1)},
            "2_mutation_after_failing_read": {"status": r2.get("status"), "message": msg(r2),
                                              "still_document_suspect": msg(r2).startswith("document-suspect: a prior call timed out on this document and its body may "),
                                              "marker": (E / "tc-10-09-a.marker").exists()},
            "3_passing_read": {"status": r3.get("status")},
            "4_mutation_after_passing_read": {"status": r4.get("status"), "message": msg(r4),
                                              "marker": (E / "tc-10-09-b.marker").exists()},
        })
        fit = await s.call("view_fit_viewport", {"doc": D})
        out["09"]["h1_view_fit_viewport"] = {"status": fit.get("status"), "message": msg(fit)}
        sv = await s.call("document_save", {"doc": D, "path": str(E / "tc-10-09-D.FCStd")})
        out["09"]["save_D_for_gui_visual"] = {"status": sv.get("status"), "message": msg(sv)}
        await s.call("document_close", {"doc": D})
        await s.call("document_close", {"doc": Ed})
    out["entry_py_document_suspect_count"] = (REPO / "src/freecad_buddy/hosts/gui_external/entry.py").read_text(encoding="utf-8").count("document-suspect")
    (E / "tc-10-0709-checks.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))


asyncio.run(main())
