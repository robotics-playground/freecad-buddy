import glob, os, threading, time
from tc05lib import *

LOG = EVIDENCE / "tc-05-02b-snapwatch.log"


def watcher(stop, docname):
    temp = os.environ.get("TEMP")
    with LOG.open("w", encoding="utf-8") as fh:
        while not stop.is_set():
            for d in glob.glob(os.path.join(temp, "FCB_TMP_snap_*")) + glob.glob(WORKDIR_TMP + "/FCB_TMP_snap_*"):
                if d in STALE:
                    continue
                try:
                    content = os.listdir(d)
                except OSError as exc:
                    content = [f"<listdir {type(exc).__name__}: {exc}>"]
                f = os.path.join(d, f"{docname}.FCStd")
                fh.write(f"{time.time():.4f} {d} {content} exists({docname}.FCStd)={os.path.exists(f)}\n")
            time.sleep(0.002)


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    for d in docs:
        if d["label"] == "TC0502":
            log.note(f"cleanup TC0502 close -> {(await m.call('document_close', {'doc': d['doc']})).get('status')}")
    doc = await body_sketch(m, "TC0502b")
    args = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)}
    preview = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_pad", "args": args}})
    token = sc(preview).get("preview_id")
    time.sleep(0.5)
    stop = threading.Event()
    t = threading.Thread(target=watcher, args=(stop, "TC0502b"), daemon=True)
    t.start(); time.sleep(0.2)
    env = await m.call("feature_pad", dict(args, doc=doc, confirm={"preview_id": token, "elicitation_action": "accept"}))
    time.sleep(0.3); stop.set(); t.join()
    lines = LOG.read_text(encoding="utf-8").splitlines()
    log.note(f"rerun feature_pad -> {short(env)}; watcher lines={len(lines)}")
    log.check("rerun: snapshot dir seen mid-operation", len(lines) >= 1, len(lines))
    log.check("rerun: dir held TC0502b.FCStd while bracket open", any("exists(TC0502b.FCStd)=True" in l or "'TC0502b.FCStd'" in l for l in lines), lines[:4])
    log.check("rerun: gone after commit", new_snaps() == [], new_snaps())
    c = await m.call("document_close", {"doc": doc})
    log.note(f"cleanup TC0502b close -> {c.get('status')}")


go("tc-05-02b", body)
