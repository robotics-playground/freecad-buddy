"""TC-11-14: the bridge writes into the user's document folder only via an explicit path (H2 proxy + H1 inline)."""
import asyncio
import os
import shutil

from tc11lib import *  # noqa: F401,F403
from tc11lib import BOX, EVIDENCE, Log, Mcp, baseline, closing, h1, sc, short

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-14"


def listing(folder):
    return {n: os.stat(os.path.join(folder, n)).st_mtime_ns for n in sorted(os.listdir(folder))}


async def sweep(m, log, host, folder):
    user_doc = os.path.join(folder, "bracket-v3.FCStd").replace("\\", "/")
    first = listing(folder)
    log.write({"host": host, "first_listing": first})
    o = await m.call("document_open", {"path": user_doc})
    d = sc(o).get("doc")
    calls = [("query_capabilities", {}), ("query_tree_summary", {"doc": d}), ("query_object", {"doc": d, "object": "Box"}),
             ("query_mass_properties", {"doc": d, "object": "Box"}), ("query_dependencies", {"doc": d}),
             ("query_sketch_info", {"doc": d, "sketch": "Box"}), ("query_placement", {"doc": d, "object": "Box"}),
             ("query_screenshot", {"doc": d}), ("verify_shape", {"doc": d, "object": "Box"}), ("verify_sketch", {"doc": d, "sketch": "Box"}),
             ("verify_recompute", {"doc": d}), ("verify_export_step", {"doc": d, "export_id": "fcb-export:none"}),
             ("verify_export_stl", {"doc": d, "export_id": "fcb-export:none"}), ("verify_export_3mf", {"doc": d, "export_id": "fcb-export:none"}),
             ("preview_dry_run", {"doc": d, "operation": {"tool": "feature_body_create", "args": {"name": "PrevBody"}}}),
             ("document_close", {"doc": d})]
    st = {"document_open": o.get("status")}
    for tool, args in calls:
        st[tool] = (await m.call(tool, args)).get("status")
    log.note(f"[{host}] read-only sweep statuses: {st}")
    post = listing(folder)
    log.write({"host": host, "post_sweep_listing": post})
    log.check(f"[{host}] reads created no file (same names)", set(post) == set(first), {"added": sorted(set(post) - set(first)), "removed": sorted(set(first) - set(post))})
    log.check(f"[{host}] reads modified no file (mtimes equal)", all(post.get(k) == v for k, v in first.items()),
              [k for k, v in first.items() if post.get(k) != v])
    log.check(f"[{host}] no FCB_TMP_prev_ entry in folder", not [n for n in post if "FCB_TMP_prev_" in n], sorted(post))
    log.check(f"[{host}] no FCB_TMP_snap_ entry in folder", not [n for n in post if "FCB_TMP_snap_" in n], "")
    o = await m.call("document_open", {"path": user_doc})
    d = sc(o).get("doc")
    stl = os.path.join(folder, "tc11-export.stl").replace("\\", "/")
    ex = await m.call("export_stl", {"doc": d, "path": stl})
    after_export = listing(folder)
    sv = await m.call("document_save", {"doc": d})
    await m.call("document_close", {"doc": d})
    third = listing(folder)
    log.write({"host": host, "third_listing": third})
    log.note(f"[{host}] export_stl {ex.get('status')}; document_save {short(sv, 200)}")
    log.check(f"[{host}] explicit export wrote exactly one new file (the requested path)",
              set(after_export) - set(post) == {"tc11-export.stl"}, sorted(set(after_export) - set(post)))
    changed = sorted(k for k in third if k in after_export and third[k] != after_export[k])
    added = sorted(set(third) - set(after_export))
    log.check(f"[{host}] document_save touched only the .FCStd (+ .FCBak allowed)",
              sv.get("status") == "OK" and set(changed) <= {"bracket-v3.FCStd"} and set(added) <= {"bracket-v3.FCStd.FCBak", "bracket-v3.FCBak"}
              and "bracket-v3.FCStd" in changed, {"changed": changed, "added": added})
    log.check(f"[{host}] no freecad-buddy-audit.jsonl in folder", "freecad-buddy-audit.jsonl" not in third, sorted(third))


async def main():
    log = Log(TAG)
    folders = {}
    for host in ("H2", "H1"):
        f = (EVIDENCE / f"{TAG}-userdocs-{host}").as_posix()
        shutil.rmtree(f, ignore_errors=True)
        os.makedirs(f)
        shutil.copy(BOX, os.path.join(f, "bracket-v3.FCStd"))
        open(os.path.join(f, "notes.txt"), "w").write("customer bracket revision notes\n")
        folders[host] = f
    log.note(f"user document folders: {folders}; audit log env FREECAD_BUDDY_AUDIT_LOG={os.environ.get('FREECAD_BUDDY_AUDIT_LOG')}")
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)
            await sweep(m, log, "H2", folders["H2"])
            async with h1(log, "h1", (EVIDENCE / f"{TAG}-h1.stderr.log").as_posix(),
                          drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE")) as hm:
                await sweep(hm, log, "H1", folders["H1"])
            await closing(m, log, doc, TAG)
    log.save()


asyncio.run(main())
