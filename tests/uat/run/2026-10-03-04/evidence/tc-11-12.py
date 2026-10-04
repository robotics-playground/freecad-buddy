"""TC-11-12: the snapshot directory is removed on commit, abort and error; keep-cases retain it (H1 inline, default workdir)."""
import asyncio
import glob
import os

from tc11lib import *  # noqa: F401,F403
from tc11lib import EVIDENCE, TEMP, Log, Mcp, apply, baseline, closing, h1, sc, short
from tc05lib import body_sketch, mut, q, sel

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-12"
H1_TMP = (EVIDENCE / "freecad-buddy-workdir" / "tmp").as_posix()  # H1 cwd = evidence; workdir default is cwd-relative


def snaps():
    return sorted(p.replace("\\", "/") for base in (TEMP, H1_TMP) for p in glob.glob(os.path.join(base, "FCB_TMP_snap_*")))


def resolve(path):
    if not path:
        return None
    return path if os.path.isabs(path) else os.path.join(str(EVIDENCE), path)


async def main():
    log = Log(TAG)
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)
            async with h1(log, "h1", (EVIDENCE / f"{TAG}-h1.stderr.log").as_posix(),
                          drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE", "FREECAD_BUDDY_WORKDIR")) as hm:
                hdoc = await body_sketch(hm, "tc11-12-snap", pad=30)
                base = snaps()
                log.note(f"baseline FCB_TMP_snap_* ($TEMP + H1 workdir tmp): {len(base)}")
                results = {}
                cases = [
                    ("commit", "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)}),
                    ("fail-rollback", "feature_fillet", {"body": "Body", "base": "Fillet", "name": "BigFillet", "edges": [sel("Fillet", "Edge1")], "radius": q(50)}),
                    ("raise", "feature_set_parameters", {"feature": "Fillet", "parameters": {"Radius": q(0)}}),
                    ("unproven", "feature_set_parameters", {"feature": "Fillet", "parameters": {"Radius": q(400)}}),
                ]
                for name, tool, args in cases:
                    pre = snaps()
                    p, env = await apply(hm, hdoc, tool, args)
                    mb = mut(env)
                    post = snaps()
                    sp = mb.get("snapshot_path")
                    results[name] = (env, mb, pre, post)
                    log.note(f"{name}: preview={p.get('status')} status={env.get('status')} rolled_back={mb.get('rolled_back')} "
                             f"rollback_proven={mb.get('rollback_proven')} snapshot_path={sp} snaps {len(pre)}->{len(post)} "
                             f"text={(env.get('text') or '')[:220]!r} detail={short(env, 220)}")
                env, mb, pre, post = results["commit"]
                log.check("Then committed mutation leaves no snapshot (count == baseline)", env.get("status") == "OK" and post == base, f"{len(base)}->{len(post)}")
                log.check("Then committed envelope snapshot_path is null", "snapshot_path" in mb and mb.get("snapshot_path") is None, mb.get("snapshot_path"))
                env, mb, pre, post = results["fail-rollback"]
                log.check("Then proven rollback leaves no snapshot (count unchanged)", post == pre, f"{len(pre)}->{len(post)} status={env.get('status')}")
                log.check("Then rolled-back envelope names proof rolled_back_verified|rolled_back_via_snapshot",
                          mb.get("rollback_proven") in ("rolled_back_verified", "rolled_back_via_snapshot"), mb.get("rollback_proven"))
                env, mb, pre, post = results["raise"]
                log.check("Then failed (raising) commit leaves no snapshot (count unchanged)", post == pre,
                          f"{len(pre)}->{len(post)} status={env.get('status')} reached_bracket={bool(mb)}")
                env, mb, pre, post = results["unproven"]
                sp = resolve(mb.get("snapshot_path"))
                text = env.get("text") or ""
                if mb.get("rolled_back") is False and env.get("status") != "OK":
                    log.check("Then UNPROVEN rollback keeps its snapshot: text prefix + named dir exists",
                              text.startswith("Mutation failed and its rollback could not be proven: ") and bool(sp) and os.path.isdir(os.path.dirname(sp)),
                              {"text": text[:120], "snapshot_path": mb.get("snapshot_path"), "dir_exists": bool(sp) and os.path.isdir(os.path.dirname(sp))})
                    log.check("Then keep-case snapshot_path is absolute (operator can act on it)", os.path.isabs(mb.get("snapshot_path") or ""),
                              mb.get("snapshot_path"))
                else:
                    log.check("Then UNPROVEN rollback keeps its snapshot", None,
                              f"reproducer did not reach the unproven path: status={env.get('status')} proven={mb.get('rollback_proven')}")
                    log.check("Then keep-case snapshot_path is absolute", None, "no keep-case reached")
                log.check("Then committed-but-unhashable keeps its snapshot", None,
                          "NOT RUN: no typed-tool input makes a committed shape unserializable (needs a fault-injected fingerprint)")
            await closing(m, log, doc, TAG)
    log.save()


asyncio.run(main())
