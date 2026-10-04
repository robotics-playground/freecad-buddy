"""TC-11-13: cleanup only touches reserved-prefix paths. Helpers run in the uv interpreter, as the TC writes them."""
import asyncio
import os
import subprocess

from tc11lib import REPO, TEMP, Log, Mcp, baseline, closing

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-13"
NR = os.path.join(TEMP, "not-reserved")


def run(code):
    r = subprocess.run(["uv", "run", "python", "-c", code], cwd=REPO, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


async def main():
    log = Log(TAG)
    os.makedirs(NR, exist_ok=True)
    for n in ("keep-a.txt", "keep-b.txt"):
        open(os.path.join(NR, n), "w").write(f"tc-11-13 {n}\n")
    log.check("Given $TEMP/not-reserved lists keep-a.txt and keep-b.txt", sorted(os.listdir(NR)) == ["keep-a.txt", "keep-b.txt"], sorted(os.listdir(NR)))
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)
            a = os.path.join(NR, "keep-a.txt")
            b = os.path.join(NR, "keep-b.txt")
            rc1, o1 = run(f"from freecad_buddy.usecases.transaction import _delete_snapshot; _delete_snapshot(r'{a}')")
            after1 = sorted(os.listdir(NR))
            rc2, o2 = run(f"from freecad_buddy.usecases.preview import _remove_tempdir; _remove_tempdir(r'{b}')")
            after2 = sorted(os.listdir(NR)) if os.path.isdir(NR) else None
            log.write({"snapshot_helper": {"rc": rc1, "out": o1, "listing": after1}, "preview_helper": {"rc": rc2, "out": o2, "listing": after2}})
            log.check("Then named snapshot file removed (keep-a.txt gone)", "keep-a.txt" not in after1, after1)
            log.check("Then sibling survived snapshot helper (keep-b.txt)", "keep-b.txt" in after1, after1)
            log.check("Then non-reserved directory survived", os.path.isdir(NR), NR)
            log.check("Then preview helper removed nothing (keep-b.txt still there)", after2 == ["keep-b.txt"], after2)
            log.check("Then neither helper raised (both exit 0)", rc1 == 0 and rc2 == 0, {"rc1": rc1, "rc2": rc2, "out": (o1 + o2)[-300:]})
            rc3, o3 = run("import tempfile,os\nfrom freecad_buddy.usecases.transaction import _delete_snapshot\n"
                          "d=tempfile.mkdtemp(prefix='FCB_TMP_snap_tc1113_')\n"
                          "[open(os.path.join(d,n),'w').write('x') for n in ('Doc.FCStd','Doc.FCStd.FCBak','extra.txt')]\n"
                          "print('minted',d,sorted(os.listdir(d)))\n_delete_snapshot(os.path.join(d,'Doc.FCStd'))\n"
                          "print('exists_after',os.path.exists(d))")
            log.check("Then reserved-prefix FCB_TMP_snap_* dir (minted for this check) removed with all contents",
                      rc3 == 0 and "exists_after False" in o3, o3)
            await closing(m, log, doc, TAG)
    log.save()


asyncio.run(main())
