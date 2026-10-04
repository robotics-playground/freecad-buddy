import glob, os, threading, time
from tc05lib import *

LOG = EVIDENCE / "tc-05-02-snapwatch.log"


def watcher(stop):
    temp = os.environ.get("TEMP")
    with LOG.open("w", encoding="utf-8") as fh:
        while not stop.is_set():
            for d in glob.glob(os.path.join(temp, "FCB_TMP_snap_*")) + glob.glob(WORKDIR_TMP + "/FCB_TMP_snap_*"):
                if d in STALE:
                    continue
                try:
                    content = os.listdir(d)
                except OSError:
                    content = ["<gone>"]
                fh.write(f"{time.time():.3f} {d} {content}\n")
            time.sleep(0.005)


async def body(m, log):
    log.check("Given no new FCB_TMP_snap_* (excluding 10 stale 2026-09-22 dirs in $TEMP)", new_snaps() == [], new_snaps())
    doc = await body_sketch(m, "TC0502")
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "Sketch"})
    s = sc(v).get("subject") or {}
    log.check("Given Sketch fully_constrained, dof 0 (verify_sketch)", s.get("fully_constrained") is True and s.get("dof") == 0, s.get("dof"))
    args = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)}
    preview = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_pad", "args": args}})
    token = sc(preview).get("preview_id")
    time.sleep(0.5)
    stop = threading.Event()
    t = threading.Thread(target=watcher, args=(stop,), daemon=True)
    t.start()
    time.sleep(0.2)
    env = await m.call("feature_pad", dict(args, doc=doc, confirm={"preview_id": token, "elicitation_action": "accept"}))
    time.sleep(0.3)
    stop.set(); t.join()
    lines = LOG.read_text(encoding="utf-8").splitlines()
    log.note(f"feature_pad -> {short(env)}; watcher lines={len(lines)}")
    log.check("snapshot dir existed mid-operation (count>=1)", len(lines) >= 1, len(lines))
    has_doc = [l for l in lines if f"{'TC0502'}.FCStd" in l]
    log.check("logged dir contained <DocumentName>.FCStd while bracket open", bool(has_doc), has_doc[:2] or lines[:3])
    log.check("snapshot gone after commit", new_snaps() == [], new_snaps())
    log.check("envelope OK and mutation.snapshot_path null", env.get("status") == "OK" and mut(env).get("snapshot_path", "MISSING") is None, mut(env).get("snapshot_path", "MISSING"))
    bak = glob.glob(os.path.join(os.environ["TEMP"], "*.FCBak")) + glob.glob(WORKDIR_TMP + "/**/*.FCBak", recursive=True)
    log.check("no orphan .FCBak in $TEMP or workdir tmp", bak == [], bak)
    fit, rec = await capture(m, doc, "tc-05-02-after.png")
    log.note(f"fit={fit}")
    log.write({"doc": doc})


go("tc-05-02", body)
