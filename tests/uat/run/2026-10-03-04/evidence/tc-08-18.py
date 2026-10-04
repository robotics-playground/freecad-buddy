"""TC-08-18: H1 headless postures. GUI part: golden box framed before/after; H1 runs never touch the GUI."""
import subprocess
import sys
from tc08lib import *  # noqa
from tc08h1 import FCB, h1, h1_env

EV = str(EVIDENCE).replace("\\", "/")
GOLD = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"
SAVED = EV + "/tc-08-18-h1-given.FCStd"
APPROVE_LOG = EV + "/tc-08-18-approve.jsonl"
WANT = ("this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as "
        "confirm.preview_id")
PAD = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": {"value": 30, "unit": "mm"}}
STAGE = sys.argv[1] if len(sys.argv) > 1 else "all"


async def gui_before(m, log):
    await close_all(m, log)
    op = await m.call("document_open", {"path": GOLD})
    gdoc = sc(op).get("doc")
    log.check("Given golden box opened in GUI", op.get("status") == "OK" and bool(gdoc), short(op))
    (EVIDENCE / "tc-08-18-gui.json").write_text(json.dumps({"gdoc": gdoc}), encoding="utf-8")
    await frame_shot(m, gdoc, "tc-08-18-before.png")


async def headless(m, log):
    chk = subprocess.run([FCB + r"\python.exe", "-c", "import FreeCAD, mcp; print('H1 ok', '.'.join(FreeCAD.Version()[:3]))"],
                         env=h1_env(), capture_output=True, text=True)
    log.check("Given FCB_PYTHON imports FreeCAD and mcp", chk.returncode == 0 and "H1 ok" in chk.stdout,
              (chk.stdout + chk.stderr).strip()[-300:])
    if os.path.exists(APPROVE_LOG):
        os.remove(APPROVE_LOG)
    # saved Given document, built on an unset-flag H1 host through preview + confirm
    async with h1(log, "given", EV + "/tc-08-18-given.stderr.log", drop=("FREECAD_BUDDY_AUTO_APPROVE",)) as hm:
        d = await body_sketch(hm, "TC0818H1")
        vs = await hm.call("verify_sketch", {"doc": d, "sketch": "Sketch"})
        sv = await hm.call("document_save", {"doc": d, "path": SAVED})
        log.check("Given saved H1 document with body + fully constrained sketch",
                  sv.get("status") == "OK" and (sc(vs).get("subject") or {}).get("fully_constrained") is True,
                  {"save": sv.get("status"), "dof": (sc(vs).get("subject") or {}).get("dof")})
    runs = {}
    for tag, extra, drop, audit in (("unset", {}, ("FREECAD_BUDDY_AUTO_APPROVE",), None),
                                    ("true", {"FREECAD_BUDDY_AUTO_APPROVE": "true"}, (), None),
                                    ("one", {"FREECAD_BUDDY_AUTO_APPROVE": "1"}, (), APPROVE_LOG)):
        if audit:
            extra = dict(extra, FREECAD_BUDDY_AUDIT_LOG=audit)
        async with h1(log, tag, EV + f"/tc-08-18-{tag}.stderr.log", extra=extra, drop=drop) as hm:
            caps = await hm.call("query_capabilities", {})
            od = await hm.call("document_open", {"path": SAVED})
            hd = sc(od).get("doc")
            r = await hm.call("feature_pad", dict(PAD, doc=hd))
            runs[tag] = {"doc": hd, "status": r.get("status"), "message": msg(r)[:300], "caps": sc(caps),
                         "rolled_back": mut(r).get("rolled_back") if r.get("status") == "OK" else None}
            print(tag, r.get("status"), msg(r)[:150])
    log.write({"runs": runs})
    log.check("flag unset fails closed with the confirm-required message",
              runs["unset"]["status"] != "OK" and runs["unset"]["message"] == WANT, runs["unset"]["message"])
    log.check("flag =true fails closed with the same message", runs["true"]["status"] != "OK" and runs["true"]["message"] == WANT,
              runs["true"]["message"])
    log.check("flag =1 returns OK with no confirm", runs["one"]["status"] == "OK", {k: runs["one"][k] for k in ("status", "message")})
    err = open(EV + "/tc-08-18-one.stderr.log", encoding="utf-8", errors="replace").read()
    log.check("=1 stderr announces 'SECURITY: mutation auto-approve ENABLED by operator flag'",
              "SECURITY: mutation auto-approve ENABLED by operator flag" in err,
              [l for l in err.splitlines() if "SECURITY" in l][:3])
    for t in ("unset", "true"):
        e = open(EV + f"/tc-08-18-{t}.stderr.log", encoding="utf-8", errors="replace").read()
        log.note(f"{t} stderr SECURITY lines: {[l for l in e.splitlines() if 'SECURITY' in l][:3]}")
    lines = open(APPROVE_LOG, encoding="utf-8").read().splitlines() if os.path.exists(APPROVE_LOG) else []
    recs = [json.loads(l) for l in lines if l.strip()]
    aa = [r for r in recs if r.get("mode") == "auto_approve"]
    log.write({"approve_log_records": recs})
    log.check("audit has a mode:auto_approve line naming tool and document handle",
              any(r.get("tool") == "feature_pad" and r.get("doc") == runs["one"]["doc"] for r in aa),
              aa[:2] or recs[:3])
    log.check("that line carries args_digest and no preview_id",
              any(r.get("args_digest") and "preview_id" not in json.dumps(r) for r in aa), aa[:1])
    cu, co = runs["unset"]["caps"], runs["one"]["caps"]
    log.check("query_capabilities reports auto-approve enabled on =1 host and disabled on unset host",
              co.get("auto_approve") is True and cu.get("auto_approve") is False,
              {"unset_keys": sorted(cu), "one_keys": sorted(co), "unset_auto_approve": cu.get("auto_approve"),
               "one_auto_approve": co.get("auto_approve")})


async def gui_after(m, log):
    gdoc = json.loads((EVIDENCE / "tc-08-18-gui.json").read_text())["gdoc"]
    mp = await m.call("query_mass_properties", {"doc": gdoc, "object": "Box"})
    log.note(f"GUI golden box volume after headless runs: {vol(mp)}")
    dl = await m.call("document_list", {})
    log.write({"gui_document_list_after_h1": sc(dl)})
    await frame_shot(m, gdoc, "tc-08-18-after.png")


async def body(m, log):
    if STAGE in ("before", "all"):
        await gui_before(m, log)
    if STAGE in ("h1", "all"):
        await headless(m, log)
    if STAGE in ("after", "all"):
        await gui_after(m, log)


go("tc-08-18-" + STAGE, body)
