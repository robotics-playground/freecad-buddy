import glob
import os
import subprocess

from tc09lib import *  # noqa

T0 = "2026-10-04 11:20"


def new_tmp():
    out = []
    for base in (os.environ.get("TEMP", ""), "C:/Users/thuan/freecad-buddy-workdir/tmp"):
        for p in glob.glob(os.path.join(base, "FCB_TMP_snap_*")) + glob.glob(os.path.join(base, "FCB_TMP_prev_*")):
            if os.path.getmtime(p) > 1791088800:  # 2026-10-04 11:20 +07:00, start of the TC-09 series
                out.append(p)
    return out


async def body(m, log):
    pid = json.loads((EVIDENCE / "fc.json").read_text())["pid"]
    log.note(f"Given recorded FreeCAD pid before the series: 32440 (fc.json {pid}); no relaunch during TC-09")
    rec = shot("tc-09-23-before.png")
    log.note(f"before capture without fit: {rec}")
    # TC-09-22 cleanup (passed): close its golden
    for d in sc(await m.call("document_list", {})).get("documents") or []:
        c = await m.call("document_close", {"doc": d["doc"]})
        log.note(f"TC-09-22 cleanup: document_close {d['label']} -> {status(c)}")
    tl = await m.session.list_tools()
    names_ = sorted(t.name for t in tl.tools)
    log.check("tools/list answers", len(names_) > 0, len(names_))
    log.check("full surface: 44 tools + debug_exec only with ALLOW_EXEC (TC); run context says 45", len(names_) == 44 + (1 if "debug_exec" in names_ else 0),
              {"count": len(names_), "debug_exec": "debug_exec" in names_})
    alive = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
    log.check("pid unchanged and alive", "freecad.exe" in alive and pid == 32440, alive.strip().splitlines()[-1][:80])
    doc, op = await open_shown(m, log)
    vs = await m.call("verify_shape", {"doc": doc, "object": "Box", "checks": [{"fn": "expect_volume", "expect": 6000, "tol": {"rel": 0.001}}]})
    ex = await m.call("export_step", {"doc": doc, "path": f"{EV}/tc-09-23-rt.step"})
    ve = await m.call("verify_export_step", {"doc": doc, "export_id": sc(ex).get("export_id")})
    vol = [c for c in sc(ve).get("checks") or [] if c.get("id") == "export_step.volume"]
    log.note(f"verify_export_step checks: {[(c.get('id'), c.get('measured'), c.get('passed')) for c in sc(ve).get('checks') or []]}")
    await frame_shot(m, doc, "tc-09-23-after.png")
    cl = await m.call("document_close", {"doc": doc})
    sts = [status(x) for x in (op, vs, ex, ve, cl)]
    log.check("round trip: every call OK", all(s == "OK" for s in sts), sts)
    meas = vol[0].get("measured") if vol else None
    mv = meas.get("value") if isinstance(meas, dict) else meas
    log.check("export_step.volume within 0.1% of 6000", isinstance(mv, (int, float)) and abs(mv - 6000) / 6000 <= 0.001, meas)
    dl = sc(await m.call("document_list", {})).get("documents") or []
    log.check("no document left open; no FCB_TMP_ document", dl == [], dl)
    nt = new_tmp()
    log.check("no FCB_TMP_snap_/prev_ left by this series", nt == [], nt)


go("tc-09-23", body)
