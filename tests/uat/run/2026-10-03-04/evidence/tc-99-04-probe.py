"""TC-99-04/05 probe: run bridge calls while a watcher records every new path under the candidate roots.

usage: tc-99-04-probe.py <doc-handle> <tag> <calls>   calls: comma list of mutation,preview,screenshot,export
Writes tc-99-<tag>-files.json (new paths seen, with first-seen time) and tc-99-<tag>-calls.jsonl.
"""
import asyncio, json, os, sys, threading, time
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

E = Path(__file__).resolve().parent
H, TAG, CALLS = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
TEMP = Path(os.environ["TEMP"])
ROOTS = {
    "workdir": (Path.home() / "freecad-buddy-workdir", True),
    "appdata": (Path(os.environ["APPDATA"]) / "FreeCAD/v1-1/freecad-buddy", True),
    "temp": (TEMP, False),
    "audit_env": (Path(os.environ.get("FREECAD_BUDDY_AUDIT_LOG", "")).parent if os.environ.get("FREECAD_BUDDY_AUDIT_LOG") else E, False),
    "evidence": (E, False),
    "fc_bin": (Path("C:/Program Files/FreeCAD 1.1/bin"), False),
}


def listing():
    seen = {}
    for key, (root, deep) in ROOTS.items():
        if not root.is_dir():
            continue
        try:
            it = root.rglob("*") if deep else root.iterdir()
            for p in it:
                if key == "temp" and not p.name.startswith("FCB_"):
                    continue
                try:
                    st = p.stat()
                    seen[str(p)] = (st.st_size, st.st_mtime)
                    if key == "temp" and p.is_dir():
                        for c in p.iterdir():
                            seen[str(c)] = (c.stat().st_size, c.stat().st_mtime)
                except OSError:
                    pass
        except OSError:
            pass
    return seen


base = listing()
new, changed = {}, {}
stop = threading.Event()


def watch():
    while not stop.is_set():
        now = listing()
        for p, v in now.items():
            if p not in base and p not in new:
                new[p] = round(time.time(), 3)
            elif p in base and base[p] != v and p not in changed:
                changed[p] = round(time.time(), 3)
        time.sleep(0.02)


async def call(s, t, a):
    r = await s.call_tool(t, a)
    txt = "".join(b.text for b in r.content if hasattr(b, "text"))
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return {"_raw": txt}


async def main():
    log = []
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for c in CALLS:
                t = time.time()
                if c == "preview":
                    res = await call(s, "preview_dry_run", {"doc": H, "operation": {"tool": "feature_body_create", "args": {"name": "PreviewOnly"}}})
                elif c == "mutation":
                    p = await call(s, "preview_dry_run", {"doc": H, "operation": {"tool": "feature_body_create", "args": {"name": f"Body{TAG}"}}})
                    res = await call(s, "feature_body_create", {"doc": H, "name": f"Body{TAG}", "confirm": {"preview_id": p["structured_content"]["preview_id"], "elicitation_action": "accept"}})
                elif c == "screenshot":
                    res = await call(s, "query_screenshot", {"doc": H})
                elif c == "export":
                    out = str(E / f"tc-99-{TAG}-export.step").replace("\\", "/")
                    res = await call(s, "export_step", {"doc": H, "path": out, "objects": ["Box"]})
                else:
                    raise SystemExit(f"unknown call {c}")
                sc = res.get("structured_content") if isinstance(res.get("structured_content"), dict) else {}
                log.append({"call": c, "t": round(t, 3), "status": res.get("status"), "detail": res.get("detail"),
                            "mutation": sc.get("mutation") and {k: sc["mutation"].get(k) for k in ("snapshot_path", "rolled_back_via_snapshot", "committed") if k in sc["mutation"]},
                            "paths": {k: v for k, v in sc.items() if isinstance(v, str) and (":/" in v or ":\\" in v or v.startswith("/"))}})
                await asyncio.sleep(0.5)
    return log


th = threading.Thread(target=watch, daemon=True)
th.start()
log = asyncio.run(main())
time.sleep(0.5)
stop.set()
th.join()
(E / f"tc-99-{TAG}-calls.jsonl").write_text("\n".join(json.dumps(x, default=str) for x in log) + "\n")
(E / f"tc-99-{TAG}-files.json").write_text(json.dumps({"new": new, "changed": changed}, indent=1))
for x in log:
    print(json.dumps(x, default=str)[:600])
print("NEW:")
for p in sorted(new, key=new.get):
    print(" ", p)
print("CHANGED:")
for p in changed:
    print(" ", p)
