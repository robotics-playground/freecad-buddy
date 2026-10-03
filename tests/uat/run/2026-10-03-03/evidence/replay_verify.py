"""Replay G3 plans over the live :8765 bridge, then grade each part with its spec's checks
through verify_shape in the spec's anchor frame. Usage: replay_verify.py case_substring ..."""

import asyncio
import json
import sys
from pathlib import Path
import yaml
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.stdio import StdioServerParameters, stdio_client
import os

REPO = Path(r"D:\Work\Personal\Sources\freecad-buddy")
PLANS = REPO / "benchmarks/g3/fault-injection/corrupted-plan"
DEV = REPO / "benchmarks/g3/dev"


async def call(s, tool, args):
    res = await s.call_tool(tool, args)
    if res.structuredContent:
        return res.structuredContent
    text = "".join(b.text for b in res.content if hasattr(b, "text"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"status": "NO_JSON", "_raw": text[:400]}


def bind(value, doc):
    if value == "$doc":
        return doc
    if isinstance(value, dict):
        return {k: bind(v, doc) for k, v in value.items()}
    if isinstance(value, list):
        return [bind(v, doc) for v in value]
    return value


# g3-dev-011 has no clean control. Its mirrored-hole-pattern plan with the planted step [6]
# replaced by the spec's placement (12 mm pivot on the origin, 8 mm linkage at +60 X) is the
# faithful build the manual check asks for.
FAITHFUL_011_STEP = {
    "tool": "sketch_add_geometry",
    "args": {
        "doc": "$doc",
        "sketch": "BoreSketch",
        "geometry": [
            {"kind": "circle", "center": [0.0, 0.0], "radius": {"value": 6.0, "unit": "mm"}},
            {"kind": "circle", "center": [60.0, 0.0], "radius": {"value": 4.0, "unit": "mm"}},
        ],
        "constraints": [
            {"type": "Radius", "first": 0, "value": {"value": 6.0, "unit": "mm"}},
            {"type": "Coincident", "first": 0, "first_pos": 3, "second": -1, "second_pos": 1},
            {"type": "Radius", "first": 1, "value": {"value": 4.0, "unit": "mm"}},
            {
                "type": "DistanceX",
                "first": -1,
                "first_pos": 1,
                "second": 1,
                "second_pos": 3,
                "value": {"value": 60.0, "unit": "mm"},
            },
            {"type": "PointOnObject", "first": 1, "first_pos": 3, "second": -1},
        ],
    },
}


def load_case(case_dir, faithful_011=False):
    case = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
    if faithful_011:
        case["id"] = "g3-dev-011-faithful-build"
        case["fault"]["expectation"] = "PASS_CLEAN"
        case["plan"][0]["args"]["label"] = case["id"]
        case["plan"][case["planted_step"]] = FAITHFUL_011_STEP
    return case


async def replay(s, case_dir, faithful_011=False):
    case = load_case(case_dir, faithful_011)
    spec = yaml.safe_load((DEV / case["spec_ref"] / "case.yaml").read_text(encoding="utf-8"))
    doc, last, failed = None, None, None
    for i, step in enumerate(case["plan"]):
        tool, args = step["tool"], bind(step["args"], doc)
        if tool == "document_create":
            env = await call(s, tool, args)
            doc = (env.get("structured_content") or {}).get("doc")
        else:
            op = {"tool": tool, "args": {k: v for k, v in args.items() if k != "doc"}}
            pv = await call(s, "preview_dry_run", {"doc": doc, "operation": op, "render": "off"})
            pid = (pv.get("structured_content") or {}).get("preview_id")
            if not pid:
                failed = (i, tool, "preview", pv.get("status"), pv.get("detail"))
                break
            env = await call(
                s, tool, {**args, "confirm": {"preview_id": pid, "elicitation_action": "accept"}}
            )
        if env.get("status") != "OK":
            failed = (i, tool, env.get("status"), env.get("detail"))
            break
        if tool.startswith("feature_") and tool not in ("feature_body_create", "feature_datum"):
            last = args.get("name")
    out = {
        "case": case["id"],
        "expectation": case["fault"]["expectation"],
        "doc": doc,
        "object": last,
        "failed": failed,
    }
    if not failed:
        vs = await call(
            s,
            "verify_shape",
            {
                "doc": doc,
                "object": last,
                "checks": spec["assertions"]["checks"],
                "anchor_frame": spec["assertions"]["anchor_frame"],
            },
        )
        sc = vs.get("structured_content") or {}
        out["status"] = vs.get("status")
        out["frame"] = (sc.get("banner") or {}).get("anchor_frame")
        out["checks"] = [
            (
                c["id"],
                c["passed"],
                c.get("measured"),
                c.get("expected"),
                (c.get("detail") or {}).get("code"),
            )
            for c in sc.get("checks", [])
        ]
        if not sc:
            out["raw"] = vs
    return out


def _headless():
    env_dir = Path.home() / "micromamba" / "envs" / "fcb"
    lib_bin = env_dir / "Library" / "bin"
    child = dict(os.environ)
    child["PYTHONPATH"] = os.pathsep.join([str(REPO / "src"), str(lib_bin)])
    child["PATH"] = os.pathsep.join(
        [str(lib_bin), str(env_dir / "Library" / "lib"), child.get("PATH", "")]
    )
    child["FREECAD_BUDDY_AUDIT_LOG"] = str(Path(__file__).with_name("audit.jsonl"))
    return StdioServerParameters(
        command=str(env_dir / "python.exe"),
        args=[
            "-m",
            "freecad_buddy.hosts.main",
            "serve",
            "--mode",
            "inline",
            "--transport",
            "stdio",
        ],
        env=child,
    )


async def run(s, wanted):
    faithful = "faithful-011" in wanted
    wanted = [w for w in wanted if w != "faithful-011"]
    cases = sorted(
        p
        for p in PLANS.iterdir()
        if (p / "case.yaml").is_file() and any(w in p.name for w in wanted)
    )
    for c in cases:
        print(json.dumps(await replay(s, c)), flush=True)
    if faithful:
        print(
            json.dumps(await replay(s, PLANS / "g3-fault-plan-mirrored-hole-pattern", True)),
            flush=True,
        )


async def main():
    args = sys.argv[1:]
    if args and args[0] == "--headless":
        with open(Path(__file__).with_name("server.stderr.log"), "w", encoding="utf-8") as err:
            async with stdio_client(_headless(), errlog=err) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    await run(s, args[1:])
        return
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            await run(s, args)


asyncio.run(main())
