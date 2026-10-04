"""G3 live-GUI replay for UAT run 2026-10-03-04.

For every case in benchmarks/g3/fault-injection/corrupted-plan/*/case.yaml: replay the plan over
the live :8765 bridge (preview_dry_run, then confirm each mutation; '$doc' bound to the
document_create handle), grade the part with verify_shape using the spec's assertions.checks and
anchor_frame, then fit with FreeCAD's own Fit All and capture the window. Planted cases are also
built from the reverted plan (score_g3_replay.reverted_plan). Each document is closed after its
capture. One JSON line per build goes to g3-replay.jsonl.

Usage: uv run python g3_gui_replay.py [case-substring ...]
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

REPO = Path(r"D:\Work\Personal\Sources\freecad-buddy")
sys.path.insert(0, str(REPO / "benchmarks" / "g3" / "fault-injection"))
from score_g3_replay import (  # noqa: E402
    _graded_object,
    bind,
    call,
    classify_planted,
    is_planted,
    reverted_plan,
)

EVIDENCE = Path(__file__).resolve().parent
PLANS = REPO / "benchmarks/g3/fault-injection/corrupted-plan"
DEV = REPO / "benchmarks/g3/dev"
OUT = EVIDENCE / os.environ.get("G3_OUT", "g3-replay.jsonl")


def gui(*args: str) -> str:
    done = subprocess.run(
        ["uv", "run", "python", str(EVIDENCE / "gui.py"), *args],
        capture_output=True, text=True, timeout=120, cwd=REPO,
    )
    return done.stdout.strip()


async def replay(session, plan: list[dict]) -> tuple[str | None, list, str | None]:
    doc, steps = None, []
    for index, step in enumerate(plan):
        tool, args = step["tool"], bind(step["args"], doc)
        if tool == "document_create":
            envelope = await call(session, tool, args)
            doc = (envelope.get("structured_content") or {}).get("doc")
        else:
            operation = {"tool": tool, "args": {k: v for k, v in args.items() if k != "doc"}}
            preview = await call(
                session, "preview_dry_run", {"doc": doc, "operation": operation, "render": "off"}
            )
            preview_id = (preview.get("structured_content") or {}).get("preview_id")
            if not preview_id:
                steps.append([index, tool, "preview", preview.get("status")])
                return doc, steps, f"step {index} {tool}: preview {preview.get('status')} {preview.get('detail')}"
            confirm = {"preview_id": preview_id, "elicitation_action": "accept"}
            envelope = await call(session, tool, {**args, "confirm": confirm})
        steps.append([index, tool, envelope.get("status")])
        if envelope.get("status") != "OK":
            return doc, steps, f"step {index} {tool}: {envelope.get('status')} {envelope.get('detail')}"
    return doc, steps, None


async def build(session, case: dict, spec: dict, plan: list[dict], kind: str) -> dict:
    plan = json.loads(json.dumps(plan))
    label = f"{case['id']}-{kind}"
    plan[0]["args"]["label"] = label
    row = {"case": case["id"], "build": kind, "spec_ref": case["spec_ref"], "label": label}
    doc, steps, error = await replay(session, plan)
    row["steps"] = steps
    if error:
        row["error"] = error
    else:
        envelope = await call(
            session,
            "verify_shape",
            {
                "doc": doc,
                "object": _graded_object(plan),
                "checks": spec["assertions"]["checks"],
                "anchor_frame": spec["assertions"]["anchor_frame"],
            },
        )
        content = envelope.get("structured_content") or {}
        row["status"] = envelope.get("status")
        row["frame"] = (content.get("banner") or {}).get("anchor_frame")
        row["checks"] = content.get("checks")
        if not isinstance(content.get("checks"), list):
            row["error"] = f"verify_shape: {envelope.get('status')} {envelope.get('detail')}"
        if kind == "planted" and isinstance(row["checks"], list):
            row["classification"] = classify_planted(row, case["detected_by"])
        mass = await call(session, "query_mass_properties", {"doc": doc, "object": _graded_object(plan)})
        row["volume"] = (mass.get("structured_content") or {}).get("volume")
    if doc:
        png = f"g3-{case['id'].removeprefix('g3-fault-plan-')}-{kind}.png"
        if os.environ.get("G3_VIEW_BUTTON"):
            row["view"] = gui("click", os.environ["G3_VIEW_BUTTON"])
            png = png.replace(".png", "-iso.png")
        row["fit"] = gui("fitall")
        time.sleep(1.0)
        row["capture"] = gui("shot", png)
        row["png"] = png
        await call(session, "document_close", {"doc": doc})
    return row


async def main() -> int:
    wanted = sys.argv[1:]
    cases = sorted(p for p in PLANS.iterdir() if (p / "case.yaml").is_file())
    if wanted:
        cases = [p for p in cases if any(w in p.name for w in wanted)]
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            with OUT.open("a", encoding="utf-8") as sink:
                for path in cases:
                    case = yaml.safe_load((path / "case.yaml").read_text(encoding="utf-8"))
                    spec = yaml.safe_load((DEV / case["spec_ref"] / "case.yaml").read_text(encoding="utf-8"))
                    builds = [("planted" if is_planted(case) else "control", case["plan"])]
                    if is_planted(case):
                        builds.append(("reverted", reverted_plan(case)))
                    for kind, plan in builds:
                        row = await build(session, case, spec, plan, kind)
                        sink.write(json.dumps(row) + "\n")
                        sink.flush()
                        failed = [c["id"] for c in row.get("checks") or [] if not c.get("passed")]
                        print(case["id"], kind, row.get("status"), row.get("classification"),
                              row.get("error"), failed, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
