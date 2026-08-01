"""Edge/corner/error-case MCP sweep for the Epic-1 tool surface (gate G0).

Complements ``run_mcp_e2e.py`` (the happy-path golden-model sweep) by driving the *failure* and
*boundary* contract over the real MCP stdio protocol against the headless H1 server: invalid
inputs, stale/mismatched ids, ambiguous selections, boundary values, planted-fault fixtures, and
read-only-invariance. It asserts the CLOSED terminal-status set (INVALID_INPUT / SPEC_FAILED / OK)
reaches the client faithfully — the layer the in-process unit tests do not exercise (they bypass
dispatch mapping and MCP serialization).

Run from the uv env: ``uv run python scripts/automation/run_mcp_edge_cases.py``. The H1 server runs
under the conda ``fcb`` env python. Writes ``_automation/edge_report.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import anyio
import yaml
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from run_mcp_e2e import (  # reuse env + envelope helpers from the happy-path harness
    GOLDEN_DIR,
    OUT_DIR,
    Report,
    _fcb_env,
    _payload,
    _status,
)

FAULT_DIR = Path(__file__).resolve().parents[2] / "benchmarks" / "g0" / "fault-injection"


async def _open_golden(session, name: str) -> str | None:
    """Open a golden model and return its doc handle, or None if the fixture is missing."""
    fcstd = GOLDEN_DIR / f"{name}.FCStd"
    if not fcstd.is_file():
        return None
    opened = await session.call_tool("document_open", {"path": str(fcstd)})
    return _payload(opened)["doc"] if _status(opened) == "OK" else None


async def _sole_object(session, handle: str) -> str | None:
    # The nested tree lives under "tree"; it was "nodes" when this harness was written, and the
    # rename went unnoticed because a None object name fails the checks rather than the call.
    tree = _payload(await session.call_tool("query_tree_summary", {"doc": handle}))
    nodes = tree.get("tree") or []
    return nodes[0]["name"] if nodes else None


async def _edge_sweep(session: ClientSession, rep: Report) -> None:
    # --- P0 invalid-input: unknown doc handle -------------------------------------------------
    r = await session.call_tool("query_tree_summary", {"doc": "fcb-doc:does-not-exist"})
    rep.record("unknown_doc_handle", _status(r) == "INVALID_INPUT", "", _status(r))

    # --- P0 invalid-input: unknown object name on a real doc ----------------------------------
    handle = await _open_golden(session, "box-10-20-30")
    if handle:
        r = await session.call_tool("query_object", {"doc": handle, "object": "NoSuchObject"})
        rep.record("unknown_object_name", _status(r) == "INVALID_INPUT", "", _status(r))

        # --- P1 boundary: an unknown parameter is refused at the input-schema gate ------------
        # query_tree_summary carried max_nodes/truncated when this harness was written; the tool
        # now bounds by depth and sets additionalProperties: False, so the boundary worth
        # asserting is that the retired parameter is rejected rather than silently ignored.
        # Rejected at the input-schema gate, so there is no envelope to read a status from —
        # asserted the same way as export_missing_path_schema above.
        r = await session.call_tool("query_tree_summary", {"doc": handle, "max_nodes": 0})
        rep.record(
            "retired_max_nodes_rejected",
            r.isError and r.structuredContent is None,
            "additionalProperties: False rejects the retired parameter",
            "SCHEMA_ERROR",
        )

        # --- P1 boundary: depth bounds the walk without dropping the root --------------------
        r = await session.call_tool("query_tree_summary", {"doc": handle, "depth": 1})
        p = _payload(r)
        ok = _status(r) == "OK" and p.get("returned_nodes") == len(p.get("tree", []))
        rep.record(
            "depth_one_returns_roots_only",
            ok,
            f"returned_nodes={p.get('returned_nodes')} roots={len(p.get('tree', []))}",
            _status(r),
        )

        # --- P1 error: export missing a schema-REQUIRED field -> MCP protocol rejection --------
        # A missing required property is rejected at the input-schema gate (isError, no envelope),
        # a layer distinct from a semantically-invalid value (which returns an INVALID_INPUT
        # envelope). Assert the schema layer here.
        obj = await _sole_object(session, handle)
        r = await session.call_tool("export_step", {"doc": handle, "objects": [obj]})
        rep.record(
            "export_missing_path_schema",
            r.isError and r.structuredContent is None,
            "schema-required rejection",
            "SCHEMA_ERROR",
        )

        # --- P1 error: export with an ambiguous no-selection on a single-object doc is fine, but
        # a selection of MULTIPLE objects to a single-shape export -> INVALID_INPUT envelope -----
        r = await session.call_tool(
            "export_step",
            {"doc": handle, "path": str(OUT_DIR / "edge_multi.step"), "objects": [obj, obj]},
        )
        rep.record("export_multi_object", _status(r) == "INVALID_INPUT", "", _status(r))

        # --- P0 error: verify with a stale/unknown export_id ----------------------------------
        r = await session.call_tool(
            "verify_export_stl", {"doc": handle, "export_id": "fcb-export:bogus"}
        )
        rep.record("stale_export_id", _status(r) == "INVALID_INPUT", "", _status(r))

        # --- P1 error: verify_export_step against an STL export_id (format mismatch) ----------
        stl = await session.call_tool(
            "export_stl", {"doc": handle, "path": str(OUT_DIR / "edge.stl"), "objects": [obj]}
        )
        if _status(stl) == "OK":
            lid = _payload(stl)["export_id"]
            r = await session.call_tool("verify_export_step", {"doc": handle, "export_id": lid})
            rep.record("verify_format_mismatch", _status(r) == "INVALID_INPUT", "", _status(r))

        # --- P0 state: a screenshot must not mutate; a second query still measures the same ---
        before = _payload(
            await session.call_tool("query_mass_properties", {"doc": handle, "object": obj})
        ).get("volume", {}).get("value")
        await session.call_tool("query_screenshot", {"doc": handle, "view": {"camera": "iso"}})
        after = _payload(
            await session.call_tool("query_mass_properties", {"doc": handle, "object": obj})
        ).get("volume", {}).get("value")
        rep.record(
            "screenshot_read_only",
            before is not None and before == after,
            f"volume {before} -> {after}",
            "OK",
        )

        # --- P1 corner: double close -> second close is INVALID_INPUT, no crash ---------------
        await session.call_tool("document_close", {"doc": handle})
        r = await session.call_tool("document_close", {"doc": handle})
        rep.record("double_close_stale", _status(r) == "INVALID_INPUT", "", _status(r))

    # --- P0 invalid-input: open a nonexistent path --------------------------------------------
    r = await session.call_tool("document_open", {"path": str(OUT_DIR / "nope-missing.FCStd")})
    rep.record("open_bad_path", _status(r) == "INVALID_INPUT", "", _status(r))

    # --- P1 corner: two-box compound -> mass properties OK with com == null -------------------
    comp = await _open_golden(session, "two-box-compound")
    if comp:
        obj = await _sole_object(session, comp)
        r = await session.call_tool("query_mass_properties", {"doc": comp, "object": obj})
        p = _payload(r)
        rep.record(
            "compound_com_null",
            _status(r) == "OK" and p.get("com") is None,
            f"com={p.get('com')}",
            _status(r),
        )
        await session.call_tool("document_close", {"doc": comp})

    # --- P0 fault-injection: verify_shape on a planted defect -> SPEC_FAILED -------------------
    await _fault_shape_case(session, rep, "wrong-volume")
    await _fault_shape_case(session, rep, "non-watertight-open-shell")


async def _fault_shape_case(session: ClientSession, rep: Report, case: str) -> None:
    """A planted-fault verify_shape fixture, given its reference checks, must FAIL (never OK).

    The checks are the correct-shape reference values from the fixture's ``case.yaml`` — the
    fixture deviates from them, so a faithful validator returns SPEC_FAILED. Passing bare (no
    checks) would let a wrong-but-valid shape slip through, so the reference checks are required.
    """
    fixture = FAULT_DIR / case
    fcstd = fixture / "fixture.FCStd"
    case_yaml = fixture / "case.yaml"
    if not fcstd.is_file() or not case_yaml.is_file():
        rep.record(f"fault_shape:{case}", False, "fixture missing", "MISSING")
        return
    checks = (yaml.safe_load(case_yaml.read_text(encoding="utf-8")).get("assertions") or {}).get(
        "checks", []
    )
    opened = await session.call_tool("document_open", {"path": str(fcstd)})
    if _status(opened) != "OK":
        rep.record(f"fault_shape:{case}", False, "open failed", _status(opened))
        return
    handle = _payload(opened)["doc"]
    obj = await _sole_object(session, handle)
    r = await session.call_tool("verify_shape", {"doc": handle, "object": obj, "checks": checks})
    # The defect must be caught: a clean OK on a planted fault is the failure we are guarding against.
    rep.record(f"fault_shape:{case}", _status(r) == "SPEC_FAILED", f"status={_status(r)}", _status(r))
    await session.call_tool("document_close", {"doc": handle})


async def _run() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    stderr_path = OUT_DIR / "edge.stderr.log"
    py, child_env = _fcb_env()
    if not Path(py).is_file():
        print(f"fcb env python not found at {py}; run the micromamba setup first", file=sys.stderr)
        return 2

    params = StdioServerParameters(
        command=py,
        args=["-m", "freecad_buddy.hosts.main", "serve", "--mode", "inline", "--transport", "stdio"],
        env=child_env,
    )
    rep = Report()
    print("Spawning headless H1 server + running the edge/corner/error sweep...\n")
    with open(stderr_path, "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await _edge_sweep(session, rep)

    result = rep.summary()
    (OUT_DIR / "edge_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n{result['passed']}/{result['total']} edge checks passed")
    print(f"report: {OUT_DIR / 'edge_report.json'}")
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(anyio.run(_run))
