"""TC-11-10: reserved-prefix temporary documents never leak into document_list (H2 proxy + H1 inline)."""
import asyncio
import glob
import os

from tc11lib import *  # noqa: F401,F403
from tc11lib import BOX, EVIDENCE, TEMP, Log, Mcp, baseline, closing, fingerprint, h1, sc, short
from tc04lib import WORKDIR_TMP

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-10"


def tmp_entries():
    out = set()
    for base in (TEMP, WORKDIR_TMP):
        for p in glob.glob(os.path.join(base, "FCB_TMP_*")):
            out.add(p.replace("\\", "/"))
    return out


def handles(env):
    return {(d.get("doc"), d.get("label"), d.get("name")) for d in sc(env).get("documents") or []}


async def sequence(m, log, host, doc):
    t0 = tmp_entries()
    l0 = await m.call("document_list", {})
    h0 = handles(l0)
    log.check(f"[{host}] baseline list has no FCB_TMP_ name", "FCB_TMP_" not in str(h0), sorted(map(str, h0)))
    fp0, _ = await fingerprint(m, doc)
    pv = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_body_create", "args": {"name": "PrevBody"}}})
    log.check(f"[{host}] preview returned terminal envelope in closed set",
              pv.get("status") in ("OK", "SPEC_FAILED", "RECOMPUTE_ERROR", "TIMEOUT", "OOM_KILLED", "WORKER_CRASHED", "INVALID_INPUT"),
              short(pv))
    step = (EVIDENCE / f"{TAG}-{host}-box.step").as_posix()
    ex = await m.call("export_step", {"doc": doc, "path": step})
    eid = sc(ex).get("export_id")
    ve = await m.call("verify_export_step", {"doc": doc, "export_id": eid}) if eid else {"status": "NO_EXPORT_ID", "detail": short(ex)}
    log.note(f"[{host}] export_step {ex.get('status')} export_id={eid}; verify_export_step {ve.get('status')} {short(ve, 200)}")
    l1 = await m.call("document_list", {})
    h1_ = handles(l1)
    log.check(f"[{host}] no FCB_TMP_prev_ handle after", "FCB_TMP_prev_" not in str(h1_), sorted(map(str, h1_)))
    log.check(f"[{host}] no FCB_TMP_ handle (export re-import) after", "FCB_TMP_" not in str(h1_), "")
    log.check(f"[{host}] final handle set == baseline", h1_ == h0, {"added": sorted(map(str, h1_ - h0)), "removed": sorted(map(str, h0 - h1_))})
    fp1, _ = await fingerprint(m, doc)
    log.check(f"[{host}] user document fingerprint unchanged", fp0 is not None and fp0 == fp1, f"{str(fp0)[:16]} -> {str(fp1)[:16]}")
    t1 = tmp_entries()
    new = sorted(t1 - t0)
    log.check(f"[{host}] no FCB_TMP_prev_* dir remains on disk ($TEMP + workdir tmp)", not [p for p in new if "FCB_TMP_prev_" in p], new)
    log.note(f"[{host}] all new FCB_TMP_* entries after the sequence: {new}")


async def main():
    log = Log(TAG)
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)
            await sequence(m, log, "H2", doc)
            async with h1(log, "h1", (EVIDENCE / f"{TAG}-h1.stderr.log").as_posix(),
                          drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE")) as hm:
                hdoc = sc(await hm.call("document_open", {"path": BOX})).get("doc")
                await sequence(hm, log, "H1", hdoc)
            await closing(m, log, doc, TAG)
    log.save()


asyncio.run(main())
