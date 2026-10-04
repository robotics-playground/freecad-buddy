"""TC-11-15: the audit log is append-only (H1 inline x2 sequential batches, then two concurrent H1 writers)."""
import asyncio
import hashlib
import json
import os
import subprocess

from tc11lib import *  # noqa: F401,F403
from tc11lib import EVIDENCE, REPO, Log, Mcp, apply, baseline, closing, h1, sc
from tc05lib import body_sketch

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-15"
AUDIT = (EVIDENCE / f"{TAG}-append.jsonl").as_posix()
CONC = (EVIDENCE / f"{TAG}-concurrent.jsonl").as_posix()


async def batch(log, tag, path, label):
    async with h1(log, tag, (EVIDENCE / f"{TAG}-{tag}.stderr.log").as_posix(), extra={"FREECAD_BUDDY_AUDIT_LOG": path},
                  drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE")) as hm:
        await body_sketch(hm, label, pad=5)


async def main():
    log = Log(TAG)
    for p in (AUDIT, CONC):
        if os.path.exists(p):
            os.remove(p)
    log.check("Given scratch audit-log path set for the H1 children", True, f"FREECAD_BUDDY_AUDIT_LOG={AUDIT}")
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)
            await batch(log, "batch1", AUDIT, "tc11-15-a")
            raw1 = open(AUDIT, "rb").read()
            n1 = raw1.count(b"\n")
            d1 = hashlib.sha256(raw1).hexdigest()
            log.note(f"after batch 1: {n1} lines, sha256 {d1[:16]}")
            await batch(log, "batch2", AUDIT, "tc11-15-b")
            raw2 = open(AUDIT, "rb").read()
            n2 = raw2.count(b"\n")
            head = b"".join(raw2.splitlines(keepends=True)[:n1])
            log.check("Then second batch only appended: first N lines byte-identical", head == raw1, f"N={n1}")
            log.check("Then line count grew", n2 > n1, f"{n1} -> {n2}")
            log.check("Then digest of first N lines == batch-1 digest", hashlib.sha256(head).hexdigest() == d1, d1[:16])
            greps = open(EVIDENCE / f"{TAG}-greps.txt", encoding="utf-8").read().split("$ ")[1:]
            o1, o2, o3 = [" | ".join(b.splitlines()[1:]).strip() for b in greps]
            log.check("Then file opened append-only: grep returns line 46", o1.startswith("46:"), o1)
            log.check("Then no bridge tool reads the audit log: grep returns nothing (TC literal)", o2 == "", o2)
            log.note("grep hit is a docstring in documents.py:40 (workdir env-var precedent), not a read of the audit file")
            log.check("Then no rotation/truncation: grep returns nothing (TC literal)", o3 == "", o3)
            log.note("grep hit is the module docstring audit_log.py:7 'never truncates, rotates, or reads it' - no code path")
            await asyncio.gather(batch(log, "conc-A", CONC, "tc11-15-c1"), batch(log, "conc-B", CONC, "tc11-15-c2"))
            bad = []
            lines = open(CONC, encoding="utf-8").read().splitlines()
            for i, ln in enumerate(lines):
                try:
                    json.loads(ln)
                except json.JSONDecodeError:
                    bad.append(i)
            tools = {}
            for ln in lines:
                rec = json.loads(ln) if ln else {}
                tools[rec.get("doc", {}).get("handle", "-")] = tools.get(rec.get("doc", {}).get("handle", "-"), 0) + 1
            log.check("Then concurrent two-writer run: every line parses as JSON, no interleaved partial line",
                      not bad and len(lines) > 0, {"lines": len(lines), "unparsable": bad, "per_doc": tools})
            await closing(m, log, doc, TAG)
    log.save()


asyncio.run(main())
