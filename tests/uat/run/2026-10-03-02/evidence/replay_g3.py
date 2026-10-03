"""Replay G3 corrupted-plan cases through the live :8765 bridge and measure the result.

Usage: replay_g3.py [case_id_substring ...]   (default: every corrupted-plan case)
Each mutation step runs preview_dry_run, then the tool with the returned preview_id (AD-5).
Documents are left open for the visual check.
"""
import asyncio, json, sys
from pathlib import Path

import yaml
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

REPO = Path(r"D:\Work\Personal\Sources\freecad-buddy")
PLANS = REPO / "benchmarks/g3/fault-injection/corrupted-plan"
DEV = REPO / "benchmarks/g3/dev"
NO_PREVIEW = {"document_create"}


async def call(s, tool, args):
    res = await s.call_tool(tool, args)
    text = "".join(b.text for b in res.content if hasattr(b, "text"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"status": "NO_JSON", "_raw": text[:300]}


def bind(value, doc):
    if value == "$doc":
        return doc
    if isinstance(value, dict):
        return {k: bind(v, doc) for k, v in value.items()}
    if isinstance(value, list):
        return [bind(v, doc) for v in value]
    return value


def short(env):
    d = env.get("detail") or {}
    if isinstance(d, dict):
        d = {k: d.get(k) for k in ("code", "message") if d.get(k)}
    return f"{env.get('status')} {json.dumps(d)[:220]}"


async def replay(s, case_dir):
    case = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
    spec = yaml.safe_load((DEV / case["spec_ref"] / "case.yaml").read_text(encoding="utf-8"))
    vol_expect = next((c["expect"] for c in spec["assertions"]["checks"] if c["fn"] == "expect_volume"), None)
    doc, last_feature, failed = None, None, None
    for i, step in enumerate(case["plan"]):
        tool, args = step["tool"], bind(step["args"], doc)
        if tool in NO_PREVIEW:
            env = await call(s, tool, args)
            if env.get("status") == "OK":
                doc = env["structured_content"]["doc"]
        else:
            pv = await call(s, "preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": {k: v for k, v in args.items() if k != "doc"}}, "render": "off"})
            pid = (pv.get("structured_content") or {}).get("preview_id")
            if not pid:
                failed = (i, tool, "preview: " + short(pv))
                break
            env = await call(s, tool, {**args, "confirm": {"preview_id": pid, "elicitation_action": "accept"}})
        if env.get("status") != "OK":
            failed = (i, tool, short(env))
            break
        if tool.startswith("feature_") and tool not in ("feature_body_create", "feature_datum"):
            last_feature = args.get("name")
    result = {"case": case["id"], "planted": case["fault"]["expectation"], "planted_step": case.get("planted_step"),
              "steps": len(case["plan"]), "doc": doc, "failed": failed, "vol_expect": vol_expect}
    if not failed and last_feature:
        mp = (await call(s, "query_mass_properties", {"doc": doc, "object": last_feature})).get("structured_content", {})
        result["volume"] = (mp.get("volume") or {}).get("value")
        result["bbox"] = mp.get("bounding_box") or mp.get("bbox")
        vs = await call(s, "verify_shape", {"doc": doc, "object": last_feature})
        result["verify_shape"] = vs.get("status")
        result["object"] = last_feature
    return result


async def main():
    wanted = sys.argv[1:]
    cases = sorted(p for p in PLANS.iterdir() if (p / "case.yaml").is_file() and (not wanted or any(w in p.name for w in wanted)))
    out = []
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for c in cases:
                res = await replay(s, c)
                out.append(res)
                print(json.dumps(res), flush=True)
    ok = sum(1 for r in out if not r["failed"])
    print(f"REPLAYED {ok}/{len(out)} without a failing step")


asyncio.run(main())
