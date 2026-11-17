"""Re-run a runner scenario's steps by MCP against the FreeCAD already running, capturing between steps.

Used by the gate run's §9 agent review (deferred-work goal 3 rule): a before-capture or between-step
Given named in an agent_check is taken by re-running the scenario's steps up to that step.

    uv run python p0_rerun.py <scenario.json> <tag> [--at N ...] [--upto K]

``--at N`` captures the window after N steps have run (0: after the document reset, before any
step) to ``evidence/<tag>-at<N>.png``. ``--fit-at N`` clicks the GUI Fit All toolbar button before that capture. ``--edit-at N:Sketch`` opens Sketch in Sketcher edit mode for that capture and closes it after
(left open after the last step). ``--upto K`` stops after K steps (default: all). Every step
call and result goes to ``evidence/<tag>-mcp.jsonl``. The FreeCAD is the one running, started with
``-M tests/uat/probe`` and a temporary ``-u`` profile; the script never starts or ends it.
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "tests" / "uat" / "runner"))

import capture  # noqa: E402
import p0_cam  # noqa: E402
import p0_edit  # noqa: E402
import p0_gui  # noqa: E402
import launch  # noqa: E402
import mcp_client  # noqa: E402
import run  # noqa: E402
import scenario as scenario_file  # noqa: E402
from scenario import substitute  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent


class _Process:
    def __init__(self, pid):
        self.pid = pid


def _edit(client, log, code):
    for entry in client.call("document_list", {})["structured_content"]["documents"]:
        args = {"doc": entry["doc"], "code": code}
        result = client.call("script_exec", args)
        log.write(json.dumps({"edit": True, "mcp": "script_exec", "args": args, "result": result}, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario")
    parser.add_argument("tag")
    parser.add_argument("--at", type=int, action="append", default=[])
    parser.add_argument("--upto", type=int)
    parser.add_argument("--fit-at", type=int, action="append", default=[],
                        help="click the GUI Fit All toolbar button before the capture at N")
    parser.add_argument("--edit-at", action="append", default=[],
                        help="N:Sketch opens Sketch in edit mode for the capture at N, then closes it")
    parser.add_argument("--wide", action="store_true",
                        help="2400 x 1350 window, so a sketch clears the Tasks panel")
    parser.add_argument("--cam", help="x,y,z,h: aim the view at (x, y, z) with view height h mm before each capture")
    args = parser.parse_args()
    edits = dict(entry.split(":", 1) for entry in args.edit_at)
    item = scenario_file.load(Path(args.scenario))
    pids = launch.running_freecad_pids()
    assert len(pids) == 1, pids
    discovery = launch.discovery_file(pids[0])
    record = json.loads(discovery.read_text(encoding="utf-8"))
    record["user_app_data"] = str(discovery.parent.parent)
    # The runner's own output files stay as the runner wrote them.
    run_dir = EVIDENCE / "rerun"
    run_dir.mkdir(exist_ok=True)
    bindings = {"PROJECT_ROOT": REPO.as_posix(), "RUN_DIR": run_dir.as_posix()}
    log = (EVIDENCE / f"{args.tag}-mcp.jsonl").open("w", encoding="utf-8")
    with mcp_client.McpClient() as client:
        session = run.LiveSession(_Process(pids[0]), record, client)
        if args.wide:
            capture.cua("set_window_frame", {"pid": session.pid, "window_id": session.window_id,
                                             "x": 0, "y": 0, "width": 2400, "height": 1350})
        session.reset()
        steps = item["steps"][: args.upto]
        for index in range(len(steps) + 1):
            if index in args.fit_at:
                p0_gui.click_label(session.pid, session.window_id, "Fit All")
            if str(index) in edits:
                _edit(client, log, p0_edit.SET.format(name=edits[str(index)]))
                time.sleep(1.0)
            if index in args.at and args.cam:
                x, y, z, h = args.cam.split(",")
                _edit(client, log, p0_cam.CODE.format(x=x, y=y, z=z, h=h))
            if index in args.at:
                out = EVIDENCE / f"{args.tag}-at{index}.png"
                session.capture(out)
                print(f"captured after {index} steps: {out}")
            if str(index) in edits and index < len(steps):
                _edit(client, log, p0_edit.RESET)
            if index == len(steps):
                break
            step = steps[index]
            if "menu" in step:
                attempts = session.menu(step["menu"])
                entry = {"i": index + 1, "menu": step["menu"], "attempts": attempts}
            else:
                call_args = substitute(step.get("args", {}), bindings)
                result = session.call(step["mcp"], call_args)
                if "name" in step:
                    bindings[step["name"]] = result
                entry = {"i": index + 1, "name": step.get("name"), "mcp": step["mcp"],
                         "args": call_args, "result": result}
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
            status = entry.get("result", {}).get("status") if isinstance(entry.get("result"), dict) else None
            print(f"step {index + 1} {step.get('name') or step.get('mcp') or step.get('menu')}: {status}")
    print(f"pid={session.pid} window_id={session.window_id}")


if __name__ == "__main__":
    main()
