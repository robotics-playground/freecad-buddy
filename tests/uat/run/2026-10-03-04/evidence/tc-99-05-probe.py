"""TC-99-05: two failing mutations in a scratch document keep their snapshots; record where they land."""
import asyncio, json, os, glob, threading, time
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

E = Path(__file__).resolve().parent
TEMP = os.environ["TEMP"]
WORK = str(Path.home() / "freecad-buddy-workdir")
out = {"temp_snap_before": len(glob.glob(os.path.join(TEMP, "FCB_TMP_snap_*"))),
       "work_snap_before": sorted(glob.glob(os.path.join(WORK, "tmp", "FCB_TMP_snap_*")))}
log = []


async def call(s, t, a, confirm=True):
    if confirm:
        p = await call(s, "preview_dry_run", {"doc": a["doc"], "operation": {"tool": t, "args": {k: v for k, v in a.items() if k != "doc"}}}, False)
        a = {**a, "confirm": {"preview_id": p["structured_content"]["preview_id"], "elicitation_action": "accept"}}
    r = await s.call_tool(t, a)
    d = json.loads("".join(b.text for b in r.content if hasattr(b, "text")))
    m = ((d.get("structured_content") or {}).get("mutation") or {}) if isinstance(d.get("structured_content"), dict) else {}
    log.append({"tool": t, "status": d.get("status"), "detail": d.get("detail"),
                "snapshot_path": m.get("snapshot_path"), "rolled_back": m.get("rolled_back"), "rollback_proven": m.get("rollback_proven")})
    return d


RECT = [{"kind": "line_segment", "start": [0, 0], "end": [20, 0]}, {"kind": "line_segment", "start": [20, 0], "end": [20, 30]},
        {"kind": "line_segment", "start": [20, 30], "end": [0, 30]}, {"kind": "line_segment", "start": [0, 30], "end": [0, 0]}]
CONS = [{"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1}, {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
        {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1}, {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
        {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2}, {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": 20, "unit": "mm"}},
        {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": {"value": 30, "unit": "mm"}},
        {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1}]


async def main():
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            d = await call(s, "document_create", {"label": "TC9905Scratch"}, False)
            h = d["structured_content"]["doc"]
            out["scratch_doc"] = h
            await call(s, "feature_body_create", {"doc": h, "name": "B"})
            await call(s, "sketch_create", {"doc": h, "name": "S", "body": "B", "plane": "XY"})
            await call(s, "sketch_add_geometry", {"doc": h, "sketch": "S", "geometry": RECT, "constraints": CONS})
            for n in ("PadFail1", "PadFail2"):
                await call(s, "feature_pad", {"doc": h, "body": "B", "profile": "S", "name": n, "length": {"value": 10, "unit": "mm"},
                                              "second_length": {"value": 4, "unit": "mm"}, "up_to": "?TwoLengths"})
            await call(s, "document_close", {"doc": h}, False)


seen = {}
stop = threading.Event()


def watch():
    while not stop.is_set():
        for root in (os.path.join(WORK, "tmp"), TEMP):
            try:
                for n in os.listdir(root):
                    if n.startswith("FCB_TMP_snap_") and os.path.join(root, n) not in seen:
                        full = os.path.join(root, n)
                        try:
                            seen[full] = {"t": round(time.time(), 3), "contents": os.listdir(full)}
                        except OSError:
                            seen[full] = {"t": round(time.time(), 3), "contents": None}
            except OSError:
                pass
        time.sleep(0.002)


base_seen = set(glob.glob(os.path.join(TEMP, "FCB_TMP_snap_*")))
th = threading.Thread(target=watch, daemon=True)
th.start()
asyncio.run(main())
stop.set()
th.join()
out["snap_dirs_seen_during_run"] = {k: v for k, v in seen.items() if k not in base_seen}
out["calls"] = log
out["temp_snap_after"] = len(glob.glob(os.path.join(TEMP, "FCB_TMP_snap_*")))
out["work_snap_after"] = sorted(glob.glob(os.path.join(WORK, "tmp", "FCB_TMP_snap_*")))
out["work_snap_after_contents"] = {d: os.listdir(d) for d in out["work_snap_after"]}
kept = [c["snapshot_path"] for c in log if c["snapshot_path"]]
out["kept_paths"] = kept
out["kept_abs"] = [os.path.abspath(p) for p in kept]
out["kept_exists_from_probe_cwd"] = [os.path.exists(p) for p in kept]
out["kept_exists_under_gui_workdir"] = [os.path.exists(os.path.join(str(Path.home()), p)) for p in kept]
out["parents"] = [os.path.basename(os.path.dirname(p)) for p in kept]
(E / "tc-99-05-probe-run2.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))
