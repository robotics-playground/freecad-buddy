"""Story 11.3 GUI UAT over the live :8765 bridge.

Usage: uat.py a|b <audit log path>

a -- FreeCAD started with FREECAD_BUDDY_AUTO_APPROVE unset: every mutation, the pad included, is
     sent without confirm and must apply.
b -- FreeCAD started with FREECAD_BUDDY_AUTO_APPROVE=0: setup runs through preview_dry_run; then a
     feature_pad without confirm and a Visibility+Length write must be refused, and a
     Visibility-only write must apply.

Prints one PASS/FAIL row per check and the approval audit lines this run wrote.
"""

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MODE, AUDIT = sys.argv[1], sys.argv[2]
rows = []


def rec(name, ok, detail=""):
    rows.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:44} {detail}", flush=True)


async def call(s, tool, args):
    res = await s.call_tool(tool, args)
    text = "".join(b.text for b in res.content if hasattr(b, "text"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"status": "NO_JSON", "_raw": text[:300]}


async def mutate(s, doc, tool, args, gated):
    """Apply ``tool``; through a preview token when the host runs the confirm gate."""
    if gated:
        pv = await call(
            s, "preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": args}, "render": "off"}
        )
        args = {**args, "confirm": {"preview_id": pv["structured_content"]["preview_id"]}}
    env = await call(s, tool, {"doc": doc, **args})
    rec(f"apply {tool}", env.get("status") == "OK", f"{env.get('status')} {env.get('detail') or ''}"[:140])
    return env


def line(a, b):
    return {"kind": "line_segment", "start": a, "end": b}


def mm(v):
    return {"value": v, "unit": "mm"}


SKETCH = {
    "sketch": "Profile",
    "geometry": [line([0, 0], [20, 0]), line([20, 0], [20, 10]), line([20, 10], [0, 10]), line([0, 10], [0, 0])],
    "constraints": [
        {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
        {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
        {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1},
        {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
        {"type": "Horizontal", "first": 0},
        {"type": "Horizontal", "first": 2},
        {"type": "Vertical", "first": 1},
        {"type": "Vertical", "first": 3},
        {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
        {"type": "DistanceX", "first": 0, "value": mm(20)},
        {"type": "DistanceY", "first": 1, "value": mm(10)},
    ],
}
PAD = {"body": "Body", "profile": "Profile", "name": "Plate", "length": mm(5)}


def approvals(doc):
    with open(AUDIT, encoding="utf-8") as handle:
        records = [json.loads(text) for text in handle if text.strip()]
    return [r for r in records if r.get("event") == "approval" and (r.get("doc") or {}).get("handle") == doc]


async def main():
    gated = MODE == "b"
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            doc = (await call(s, "document_create", {"label": f"uat_11_3_{MODE}"}))["structured_content"]["doc"]
            print(f"DOC {doc}")
            await mutate(s, doc, "feature_body_create", {"name": "Body"}, gated)
            await mutate(s, doc, "sketch_create", {"name": "Profile", "plane": "XY", "body": "Body"}, gated)
            await mutate(s, doc, "sketch_add_geometry", SKETCH, gated)
            pad = await mutate(s, doc, "feature_pad", PAD, gated)
            block = pad["structured_content"]["mutation"]
            rec(
                "pad post-verify passed, not rolled back",
                block["post_verify"]["passed"] and not block["rolled_back"],
                json.dumps({"changed": block["changed"]})[:140],
            )
            mp = (await call(s, "query_mass_properties", {"doc": doc, "object": "Plate"}))["structured_content"]
            vol = (mp.get("volume") or {}).get("value")
            rec("Plate volume == 1000 mm3", vol is not None and abs(vol - 1000) < 1e-3, f"vol={vol}")

            if gated:
                refused = await call(s, "feature_pad", {"doc": doc, **PAD, "name": "Plate2"})
                rec(
                    "feature_pad without confirm refused",
                    refused.get("status") == "INVALID_INPUT",
                    f"{refused.get('status')} {(refused.get('detail') or {}).get('message', '')}"[:140],
                )
                mixed = await call(
                    s,
                    "feature_set_parameters",
                    {"doc": doc, "feature": "Plate", "parameters": {"Visibility": False, "Length": mm(7)}},
                )
                rec(
                    "Visibility+Length without confirm refused",
                    mixed.get("status") == "INVALID_INPUT",
                    f"{mixed.get('status')} {(mixed.get('detail') or {}).get('message', '')}"[:140],
                )
                hide = await call(
                    s,
                    "feature_set_parameters",
                    {"doc": doc, "feature": "Plate", "parameters": {"Visibility": False}},
                )
                hblock = (hide.get("structured_content") or {}).get("mutation") or {}
                rec(
                    "Visibility-only write applies",
                    hide.get("status") == "OK" and hblock.get("changed") == [],
                    f"{hide.get('status')} changed={hblock.get('changed')} rolled_back={hblock.get('rolled_back')}",
                )
                obj = (await call(s, "query_object", {"doc": doc, "object": "Plate"}))["structured_content"]
                print("  query_object Plate Visibility:", json.dumps(obj, default=str)[:400])

            await call(s, "view_fit_viewport", {"doc": doc})

    lines = approvals(doc)
    for line_ in lines:
        print("  AUDIT", json.dumps({k: line_.get(k) for k in ("event", "tool", "approval")}))
    modes = [(x["tool"], x["approval"]["mode"]) for x in lines]
    if gated:
        rec(
            "audit: pad preview_token, hide display_state",
            ("feature_pad", "preview_token") in modes and ("feature_set_parameters", "display_state") in modes,
            str(modes[-2:]),
        )
        rec("audit: refused calls wrote no approval", len(lines) == 5, f"{len(lines)} approval lines")
    else:
        pads = [x for x in lines if x["tool"] == "feature_pad"]
        rec(
            "audit: pad auto_approve with source",
            len(pads) == 1
            and pads[0]["approval"]["mode"] == "auto_approve"
            and pads[0]["approval"].get("source") == "FREECAD_BUDDY_AUTO_APPROVE",
            json.dumps(pads[0]["approval"] if pads else None)[:200],
        )
    print(f"{sum(rows)}/{len(rows)} passed")
    return 0 if all(rows) else 1


sys.exit(asyncio.run(main()))
