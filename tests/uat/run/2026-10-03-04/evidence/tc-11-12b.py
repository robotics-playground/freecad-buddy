"""TC-11-12 addendum: (a) H1 op that raises inside the bracket (degenerate line); (b) GUI unproven-rollback keep-case
(feature_set_parameters Fillet Radius 400 reached the unproven path on the GUI in TC-05-06). Scratch GUI doc closed afterwards."""
import asyncio
import glob
import os

from tc11lib import EVIDENCE, TEMP, Log, Mcp, apply, closing, h1, sc, short
from tc05lib import body_sketch, mut, q, sel
from tc04lib import WORKDIR_TMP

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-12b"
H1_TMP = (EVIDENCE / "freecad-buddy-workdir" / "tmp").as_posix()


def snaps(*bases):
    return sorted(p.replace("\\", "/") for base in bases for p in glob.glob(os.path.join(base, "FCB_TMP_snap_*")))


async def main():
    log = Log(TAG)
    async with h1(log, "h1", (EVIDENCE / f"{TAG}-h1.stderr.log").as_posix(),
                  drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE", "FREECAD_BUDDY_WORKDIR")) as hm:
        hdoc = sc(await hm.call("document_create", {"label": "tc11-12b"})).get("doc")
        await apply(hm, hdoc, "feature_body_create", {"name": "Body"})
        await apply(hm, hdoc, "sketch_create", {"name": "Sketch", "body": "Body", "plane": "XY"})
        for label, geo in (("degenerate-line", [{"kind": "line_segment", "start": [5, 5], "end": [5, 5]}]),
                           ("zero-circle", [{"kind": "circle", "center": [0, 0], "radius": q(0)}])):
            pre = snaps(TEMP, H1_TMP)
            p, env = await apply(hm, hdoc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": geo, "constraints": []})
            post = snaps(TEMP, H1_TMP)
            mb = mut(env)
            log.note(f"{label}: preview={short(p, 200)} status={env.get('status')} mutation={bool(mb)} rolled_back={mb.get('rolled_back')} "
                     f"proven={mb.get('rollback_proven')} snaps {len(pre)}->{len(post)} detail={short(env, 300)}")
            log.write({"raise_probe": label, "reached_bracket": bool(mb), "snaps_unchanged": pre == post})
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            gdoc = await body_sketch(m, "TC1112", pad=30)
            pf, f = await apply(m, gdoc, "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)})
            log.note(f"GUI fixture fillet r2 -> {short(f)}")
            pre = snaps(TEMP, WORKDIR_TMP)
            p, env = await apply(m, gdoc, "feature_set_parameters", {"feature": "Fillet", "parameters": {"Radius": q(400)}})
            post = snaps(TEMP, WORKDIR_TMP)
            mb = mut(env)
            sp = mb.get("snapshot_path")
            full = sp if (sp and os.path.isabs(sp)) else (os.path.join(os.path.expanduser("~"), sp) if sp else None)
            text = env.get("text") or ""
            log.note(f"GUI set Radius 400: status={env.get('status')} rolled_back={mb.get('rolled_back')} proven={mb.get('rollback_proven')} "
                     f"snapshot_path={sp!r} resolved={full} snaps {len(pre)}->{len(post)} text={text[:260]!r}")
            unproven = mb.get("rolled_back") is False and env.get("status") != "OK"
            if unproven:
                log.check("Then UNPROVEN rollback keeps its snapshot: text prefix + named dir exists on disk",
                          text.startswith("Mutation failed and its rollback could not be proven: ") and bool(full) and os.path.isdir(os.path.dirname(full)),
                          {"prefix_ok": text.startswith("Mutation failed and its rollback could not be proven: "), "dir": os.path.dirname(full) if full else None})
                log.check("Then keep-case snapshot_path is an absolute path", os.path.isabs(sp or ""), sp)
            else:
                log.check("Then UNPROVEN rollback keeps its snapshot", None, f"GUI reproducer did not reach unproven: {env.get('status')} {mb.get('rollback_proven')}")
            c = await m.call("document_close", {"doc": gdoc})
            log.note(f"scratch GUI doc TC1112 closed: {c.get('status')}; kept snapshot left in place (TC: operator decides)")
            docs = sc(await m.call("document_list", {})).get("documents") or []
            box = [d for d in docs if d.get("label") == "box-10-20-30"]
            await closing(m, log, box[0]["doc"], "tc-11-12")
    log.save()


asyncio.run(main())
