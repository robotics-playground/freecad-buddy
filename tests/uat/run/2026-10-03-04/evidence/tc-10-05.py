"""TC-10-05 When/Then on H1: a ~100 s preview_dry_run held on one session, then document_list on it."""
import asyncio, glob, json, os, time
from tc10lib import E, REPO, Log, h1
log = Log("tc-10-05.jsonl")
TMPS = [os.path.expandvars(r"%TEMP%"), str(REPO / "freecad-buddy-workdir" / "tmp"), r"C:/Users/thuan/freecad-buddy-workdir/tmp"]
def prev_dirs():
    out = []
    for t in TMPS:
        try:
            out += glob.glob(os.path.join(t, "FCB_TMP_prev_*"))
        except OSError as exc:
            out.append(f"{t}: {exc}")
    return out
async def main():
    out = {"prev_dirs_before": prev_dirs()}
    async with h1(log, "05", str(E / "tc-10-05-server.stderr.log"),
                  extra={"FREECAD_BUDDY_AUDIT_LOG": str(E / "tc-10-05-audit.jsonl")}) as s:
        o = await s.call("document_open", {"path": str(E / "tc-10-slow-100.FCStd")})
        h = o["structured_content"]["doc"]; out["handle"] = h
        t = time.time()
        p = await s.call("preview_dry_run", {"doc": h, "operation": {"tool": "feature_body_create", "args": {"name": "Body"}}, "render": "off"})
        out["preview"] = {"status": p.get("status"), "seconds": round(time.time() - t, 2),
                          "keys": sorted(p), "preview_id": (p.get("structured_content") or {}).get("preview_id"),
                          "detail": p.get("detail")}
        dl = await s.call("document_list", {})
        out["document_list_same_session"] = dl.get("status")
        out["handles_listed"] = [(d.get("label"), d.get("name")) for d in dl["structured_content"]["documents"]]
        out["FCB_TMP_prev_in_list"] = [d for d in dl["structured_content"]["documents"]
                                       if str(d.get("name", "")).startswith("FCB_TMP_prev_") or str(d.get("label", "")).startswith("FCB_TMP_prev_")]
        await s.call("document_close", {"doc": h})
    out["prev_dirs_after"] = prev_dirs()
    print(json.dumps(out, indent=1)); (E / "tc-10-05-checks.json").write_text(json.dumps(out, indent=1))
asyncio.run(main())
