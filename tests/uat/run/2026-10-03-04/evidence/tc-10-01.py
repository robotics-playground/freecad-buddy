"""TC-10-01 (and the Given/visual half reused by TC-10-02). Usage: tc-10-01.py given|when|after <NN>"""
import asyncio
import json
import shutil
import subprocess
import sys
import time

from tc10lib import BOX, E, REPO, Log, gui, gui_py, h1, show_all

step, nn = sys.argv[1], sys.argv[2]
log = Log(f"tc-10-{nn}.jsonl")
state = E / f"tc-10-{nn}-state.json"


async def given():
    async with gui(log, f"{nn}-given") as g:
        o = await g.call("document_open", {"path": BOX})
        h = o["structured_content"]["doc"]
        print("open", o["status"], h)
        print("show_all", show_all())
        f = await g.call("view_fit_viewport", {"doc": h})
        print("fit", f["status"], (f.get("detail") or {}).get("message"))
        state.write_text(json.dumps({"handle": h, "fit_status": f["status"]}))
    if f["status"] != "OK":
        print("gui fitall", gui_py("fitall"))
        time.sleep(1)
    print(gui_py("shot", f"tc-10-{nn}-before.png"))


async def six_reads():
    """Six back-to-back reads on one H1 connection with entry/exit timestamps per call."""
    async with h1(log, f"{nn}-six", str(E / f"tc-10-{nn}-six.stderr.log")) as s:
        o = await s.call("document_open", {"path": BOX})
        h = o["structured_content"]["doc"]
        seq = [("query_tree_summary", {"doc": h}), ("query_object", {"doc": h, "object": "Box"}),
               ("query_mass_properties", {"doc": h, "object": "Box"}), ("query_placement", {"doc": h, "object": "Box"}),
               ("verify_shape", {"doc": h, "object": "Box"}), ("query_dependencies", {"doc": h, "object": "Box"})]
        spans = []
        for tool, args in seq:
            t0 = time.time()
            env = await s.call(tool, args)
            spans.append({"tool": tool, "start": t0, "end": time.time(), "status": env.get("status")})
        await s.call("document_close", {"doc": h})
    overlaps = [i for i in range(1, len(spans)) if spans[i]["start"] < spans[i - 1]["end"]]
    out = {"request_order": [t for t, _ in seq], "spans": spans, "overlaps": overlaps}
    (E / f"tc-10-{nn}-six-spans.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"order": [s["tool"] for s in spans], "status": [s["status"] for s in spans],
                      "overlaps": overlaps,
                      "durations": [round(s["end"] - s["start"], 3) for s in spans]}))


def when():
    t0 = time.time()
    r = subprocess.run(["uv", "run", "python", "scripts/automation/run_mcp_e2e.py"], cwd=str(REPO),
                       capture_output=True, text=True)
    (E / f"tc-10-{nn}-e2e-stdout.txt").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr)
    shutil.copy(REPO / "_automation" / "e2e_report.json", E / f"tc-10-{nn}-e2e_report.json")
    shutil.copy(REPO / "_automation" / "server.stderr.log", E / f"tc-10-{nn}-server.stderr.log")
    print("e2e exit", r.returncode, "wall", round(time.time() - t0, 1))
    print(r.stdout[-1500:])
    if nn == "01":
        asyncio.run(six_reads())


async def after():
    h = json.loads(state.read_text())["handle"]
    async with gui(log, f"{nn}-after") as g:
        f = await g.call("view_fit_viewport", {"doc": h})
        print("fit", f["status"], (f.get("detail") or {}).get("message"))
    if f["status"] != "OK":
        print("gui fitall", gui_py("fitall"))
        time.sleep(1)
    print(gui_py("shot", f"tc-10-{nn}-after.png"))


async def cleanup():
    h = json.loads(state.read_text())["handle"]
    async with gui(log, f"{nn}-cleanup") as g:
        c = await g.call("document_close", {"doc": h})
        print("close", c["status"])


if step == "given":
    asyncio.run(given())
elif step == "when":
    when()
elif step == "after":
    asyncio.run(after())
elif step == "cleanup":
    asyncio.run(cleanup())
