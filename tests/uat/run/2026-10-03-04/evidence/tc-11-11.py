"""TC-11-11: a preview TempDoc is removed on every exit path (H1 inline)."""
import asyncio
import glob
import os

from tc11lib import *  # noqa: F401,F403
from tc11lib import EVIDENCE, TEMP, Log, Mcp, baseline, closing, h1, sc, short
from tc05lib import body_sketch, q

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-11"
WORK = (EVIDENCE / f"{TAG}-workdir").as_posix()
CLOSED = ("OK", "SPEC_FAILED", "RECOMPUTE_ERROR", "TIMEOUT", "OOM_KILLED", "WORKER_CRASHED", "INVALID_INPUT")


def prev_dirs():
    return sorted(p.replace("\\", "/") for base in (TEMP, WORK + "/tmp") for p in glob.glob(os.path.join(base, "FCB_TMP_prev_*")))


def msg(e):
    return (e.get("detail") or {}).get("message") or ""


async def main():
    log = Log(TAG)
    os.makedirs(WORK, exist_ok=True)
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)
            async with h1(log, "h1", (EVIDENCE / f"{TAG}-h1.stderr.log").as_posix(), extra={"FREECAD_BUDDY_WORKDIR": WORK},
                          drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE")) as hm:
                hdoc = await body_sketch(hm, "tc11-11-preview")
                base = prev_dirs()
                log.note(f"baseline FCB_TMP_prev_* ($TEMP + H1 workdir tmp): {len(base)} {base}")
                cases = [
                    ("success", {"tool": "feature_pad", "args": {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(5)}}),
                    ("failure", {"tool": "feature_pocket", "args": {"body": "Body", "profile": "Sketch", "name": "Pocket", "length": q(5)}}),
                    ("raise", {"tool": "feature_pad", "args": {"body": "Body", "profile": "NoSuchSketch", "name": "Pad2", "length": q(5)}}),
                ]
                envs = {}
                for name, op in cases:
                    env = await hm.call("preview_dry_run", {"doc": hdoc, "operation": op})
                    envs[name] = env
                    now = prev_dirs()
                    lst = await hm.call("document_list", {})
                    labels = [(d.get("label"), d.get("name")) for d in sc(lst).get("documents") or []]
                    log.note(f"{name}: status={env.get('status')} validity={((sc(env).get('diff') or {}).get('validity'))} "
                             f"msg={msg(env)[:200]!r} prev_dirs={len(now)} docs={labels}")
                    log.check(f"Then {name} path leaves nothing: FCB_TMP_prev_* count unchanged", now == base, {"count": len(now), "new": sorted(set(now) - set(base))})
                    log.check(f"Then no FCB_TMP_prev_ handle in document_list after {name}", "FCB_TMP_prev_" not in str(labels), labels)
                f, x = envs["failure"], envs["raise"]
                fdiff = sc(f).get("diff") or {}
                log.check("Then failing preview returned an envelope with SPEC_FAILED or RECOMPUTE_ERROR",
                          f.get("status") in ("SPEC_FAILED", "RECOMPUTE_ERROR"),
                          {"status": f.get("status"), "validity": fdiff.get("validity"), "msg": msg(f)[:200]})
                log.check("Then raising preview returned closed-set status with detail.message",
                          x.get("status") in CLOSED and bool(msg(x)), {"status": x.get("status"), "msg": msg(x)[:200]})
                causes = {k: msg(v) or json.dumps(fdiff.get("validity")) for k, v in envs.items()}
                log.check("Then cleanup never masked the outcome: no message names a cleanup failure",
                          all("cleanup" not in c.lower() and "rmdir" not in c.lower() and "tempdoc" not in c.lower() for c in causes.values()),
                          {k: c[:160] for k, c in causes.items()})
            await closing(m, log, doc, TAG)
    log.save()


import json  # noqa: E402

asyncio.run(main())
