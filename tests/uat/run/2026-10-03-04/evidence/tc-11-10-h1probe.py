"""TC-11-10 follow-up: which H1 call changes the user document fingerprint (preview / export_step / verify_export_step)."""
import asyncio
from tc11lib import BOX, EVIDENCE, Log, fingerprint, h1, sc

async def main():
    log = Log("tc-11-10-h1probe")
    async with h1(log, "h1", (EVIDENCE / "tc-11-10-h1probe.stderr.log").as_posix(), drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE")) as m:
        doc = sc(await m.call("document_open", {"path": BOX})).get("doc")
        seq = [("open", None)]
        fps = [(await fingerprint(m, doc))[0]]
        fps.append((await fingerprint(m, doc))[0]); seq.append(("after a 2nd preview", None))
        ex = await m.call("export_step", {"doc": doc, "path": (EVIDENCE / "tc-11-10-H1probe-box.step").as_posix()})
        fps.append((await fingerprint(m, doc))[0]); seq.append(("after export_step", ex.get("status")))
        ve = await m.call("verify_export_step", {"doc": doc, "export_id": sc(ex).get("export_id")})
        fps.append((await fingerprint(m, doc))[0]); seq.append(("after verify_export_step", ve.get("status")))
        rc = await m.call("document_recompute", {"doc": doc})
        fps.append((await fingerprint(m, doc))[0]); seq.append(("after document_recompute", rc.get("status")))
        mp = sc(await m.call("query_mass_properties", {"doc": doc, "object": "Box"}))
        for (step, st), fp in zip(seq, fps):
            log.note(f"{step:28} status={st} fingerprint={str(fp)[:16]}")
        log.note(f"volume after all: {mp.get('volume')}")
    log.save()
asyncio.run(main())
